#if os(macOS)
import AppKit
import Foundation
import GrizzlyCore
import Observation

enum EngineState: Equatable {
    case stopped
    case starting
    case running
    case failed(String)
}

/// App-wide state: the engine connection, the library and the open project.
@MainActor
@Observable
final class AppModel {
    // Settings, persisted in UserDefaults.
    var engineDirectory: String
    var port: Int
    var profile: String

    var engineState: EngineState = .stopped
    var engineInfo: EngineInfo?
    var engineLog: [String] = []

    var projects: [ProjectSummary] = []
    private(set) var selection: String?
    var current: ProjectEnvelope?
    var exports: Exports?
    /// Latest known job per project id.
    var jobs: [String: Job] = [:]
    /// Bumped whenever renders finish so images and clips reload.
    var mediaVersion = 1

    var showNewStory = false
    var alert: String?

    private(set) var client: EngineClient
    private var engine: EngineProcess?
    private var trackedJobs: Set<String> = []

    static let profiles = ["m5pro-24gb", "m5pro-24gb-ollama", "mac-48gb", "mock"]

    private enum Keys {
        static let directory = "engineDirectory"
        static let port = "enginePort"
        static let profile = "engineProfile"
    }

    init() {
        let defaults = UserDefaults.standard
        engineDirectory = defaults.string(forKey: Keys.directory) ?? "~/Grizzly"
        let savedPort = defaults.integer(forKey: Keys.port)
        port = savedPort == 0 ? 8642 : savedPort
        profile = defaults.string(forKey: Keys.profile) ?? "m5pro-24gb"
        client = EngineClient(port: savedPort == 0 ? 8642 : savedPort)
    }

    func saveSettings() {
        let defaults = UserDefaults.standard
        defaults.set(engineDirectory, forKey: Keys.directory)
        defaults.set(port, forKey: Keys.port)
        defaults.set(profile, forKey: Keys.profile)
    }

    // MARK: Engine lifecycle

    func startEngine() async {
        guard engineState != .starting, engineState != .running else { return }
        engineState = .starting
        client = EngineClient(port: port)
        // Reuse an engine that is already running (e.g. `grizzly serve` in a terminal).
        if (try? await client.health()) != nil {
            await engineDidStart()
            return
        }
        let directory = URL(fileURLWithPath: (engineDirectory as NSString).expandingTildeInPath)
        let process = EngineProcess(configuration: .init(engineDirectory: directory, port: port, profile: profile))
        process.onOutput = { [weak self] line in
            Task { @MainActor in self?.appendLog(line) }
        }
        do {
            try process.start()
            engine = process
            _ = try await waitForEngine(client, process: process, timeout: .seconds(120))
            await engineDidStart()
        } catch {
            process.stop()
            engine = nil
            engineState = .failed(error.localizedDescription)
        }
    }

    func stopEngine() {
        engine?.stop()
        engine = nil
        engineState = .stopped
    }

    func restartEngine() async {
        saveSettings()
        stopEngine()
        await startEngine()
    }

    private func engineDidStart() async {
        engineInfo = try? await client.info()
        engineState = .running
        await refreshProjects()
        for project in projects where project.busy {
            await resumeTracking(project.id)
        }
        if let selection { await reload(selection) }
    }

    private func appendLog(_ line: String) {
        engineLog.append(line)
        if engineLog.count > 500 { engineLog.removeFirst(engineLog.count - 500) }
    }

    // MARK: Library

    func refreshProjects() async {
        do {
            projects = try await client.projects()
        } catch {
            report(error)
        }
    }

    func select(_ id: String?) {
        guard id != selection else { return }
        selection = id
        current = nil
        exports = nil
        guard let id else { return }
        Task { await reload(id) }
    }

    func reload(_ id: String) async {
        do {
            let envelope = try await client.project(id)
            let files = try await client.exports(id)
            guard selection == id else { return }
            current = envelope
            exports = files
            if envelope.busy { await resumeTracking(id) }
        } catch {
            report(error)
        }
    }

    func createStory(title: String, premise: String, format: StoryFormat, scenes: Int, shots: Int) async {
        do {
            let project = try await client.createProject(title: title, premise: premise, format: format)
            await refreshProjects()
            select(project.id)
            run(.all, StepRequest(scenes: scenes, shots: shots))
        } catch {
            report(error)
        }
    }

    func delete(_ id: String) async {
        do {
            try await client.deleteProject(id)
            if selection == id { select(nil) }
            await refreshProjects()
        } catch {
            report(error)
        }
    }

    // MARK: Jobs

    func job(for project: String) -> Job? { jobs[project] }

    func isBusy(_ project: String) -> Bool {
        if let job = jobs[project], !job.state.isFinished { return true }
        if current?.project.id == project, current?.busy == true { return true }
        return projects.first { $0.id == project }?.busy ?? false
    }

    /// Runs a pipeline step on the selected project.
    func run(_ step: PipelineStep, _ request: StepRequest = StepRequest()) {
        guard let id = selection else { return }
        Task {
            do {
                track(try await client.run(step, project: id, request))
            } catch {
                report(error)
            }
        }
    }

    private func resumeTracking(_ project: String) async {
        guard let jobs = try? await client.jobs(project: project),
              let active = jobs.last(where: { !$0.state.isFinished }) else { return }
        track(active)
    }

    private func track(_ job: Job) {
        jobs[job.project] = job
        guard !trackedJobs.contains(job.id) else { return }
        trackedJobs.insert(job.id)
        if current?.project.id == job.project { current?.busy = true }
        Task {
            defer { trackedJobs.remove(job.id) }
            do {
                let final = try await client.waitForJob(job.id) { [weak self] update in
                    self?.jobs[update.project] = update
                }
                mediaVersion += 1
                if final.state == .failed {
                    alert = "\(Self.title(of: final.stage ?? final.step)) failed: \(final.error ?? "unknown error")"
                }
                await refreshProjects()
                if selection == job.project { await reload(job.project) }
            } catch {
                report(error)
            }
        }
    }

    static func title(of step: String) -> String {
        switch step {
        case "all": "The run"
        case "bible": "Writing the story bible"
        case "outline": "Outlining"
        case "shots": "Storyboarding"
        case "portraits": "Casting portraits"
        case "images": "Drawing panels"
        case "video": "Animating"
        case "comic": "The comic export"
        case "vn": "The visual novel export"
        case "animatic": "The animatic export"
        default: step.capitalized
        }
    }

    // MARK: Edits

    @discardableResult
    func updateShot(_ shot: String, _ patch: ShotPatch) async -> Bool {
        await edit { [client] id in try await client.patchShot(id, shot, patch) }
    }

    @discardableResult
    func updateCharacter(_ character: String, _ patch: CharacterPatch) async -> Bool {
        await edit { [client] id in try await client.patchCharacter(id, character, patch) }
    }

    @discardableResult
    func updateBible(_ patch: BiblePatch) async -> Bool {
        await edit { [client] id in try await client.patchBible(id, patch) }
    }

    private func edit(_ call: (String) async throws -> ProjectEnvelope) async -> Bool {
        guard let id = selection else { return false }
        do {
            current = try await call(id)
            return true
        } catch {
            report(error)
            return false
        }
    }

    // MARK: Files

    /// Served URL for a file of the selected project.
    func fileURL(_ path: String) -> URL? {
        guard let selection else { return nil }
        return client.fileURL(project: selection, path: path, version: mediaVersion)
    }

    func coverURL(_ summary: ProjectSummary) -> URL? {
        summary.cover.map { client.fileURL(project: summary.id, path: $0, version: mediaVersion) }
    }

    /// The file on disk, for opening in other apps or revealing in Finder.
    func localURL(_ path: String) -> URL? {
        guard let selection, let root = engineInfo?.projectsDir else { return nil }
        return URL(fileURLWithPath: root).appendingPathComponent(selection).appendingPathComponent(path)
    }

    func open(_ path: String?) {
        guard let path, let url = localURL(path) else { return }
        NSWorkspace.shared.open(url)
    }

    func reveal(_ path: String?) {
        guard let path, let url = localURL(path) else { return }
        NSWorkspace.shared.activateFileViewerSelecting([url])
    }

    private func report(_ error: Error) {
        alert = error.localizedDescription
    }
}
#endif
