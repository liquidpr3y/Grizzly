import Foundation
#if canImport(FoundationNetworking)
import FoundationNetworking
#endif
import XCTest
@testable import GrizzlyCore

/// Drives the real Python engine (mock models) through EngineProcess and
/// EngineClient, the same way the app does. Needs a checkout with a .venv:
/// set GRIZZLY_ENGINE_DIR to it (CI and the Linux dev box do).
final class EngineIntegrationTests: XCTestCase {
    var engine: EngineProcess!
    var client: EngineClient!
    var home: URL!

    override func setUp() async throws {
        guard let dir = ProcessInfo.processInfo.environment["GRIZZLY_ENGINE_DIR"] else {
            throw XCTSkip("Set GRIZZLY_ENGINE_DIR to a Grizzly checkout with a .venv")
        }
        home = FileManager.default.temporaryDirectory.appendingPathComponent("grizzly-swift-\(UUID().uuidString)")
        let port = Int.random(in: 20000..<40000)
        engine = EngineProcess(configuration: .init(
            engineDirectory: URL(fileURLWithPath: dir), port: port, profile: "mock",
            environment: ["GRIZZLY_HOME": home.path]
        ))
        try engine.start()
        client = EngineClient(port: port)
        _ = try await waitForEngine(client, timeout: .seconds(30))
    }

    override func tearDown() async throws {
        engine?.stop()
        if let home { try? FileManager.default.removeItem(at: home) }
    }

    func testWholeStoryThroughTheClient() async throws {
        let info = try await client.info()
        XCTAssertEqual(info.profile, "mock")
        XCTAssertTrue(info.projectsDir.hasPrefix(home.path))

        let project = try await client.createProject(title: "Swift Test", premise: "A keeper hears the sea.", format: .comic)
        XCTAssertEqual(project.format, .comic)

        var updates = 0
        let job = try await client.run(.all, project: project.id, StepRequest(scenes: 1, shots: 3))
        let finished = try await client.waitForJob(job.id, every: .milliseconds(200)) { _ in updates += 1 }
        XCTAssertEqual(finished.state, .done, finished.error ?? "")
        XCTAssertGreaterThan(updates, 0)
        XCTAssertEqual(finished.result, "exports/comic/\(project.id).pdf")
        XCTAssertEqual(finished.stage, "comic")
        XCTAssertEqual(finished.stageIndex, 3)

        let envelope = try await client.project(project.id)
        XCTAssertEqual(envelope.project.shots.count, 3)
        XCTAssertTrue(envelope.status.images && envelope.status.portraits)
        XCTAssertFalse(envelope.busy)
        let bible = try XCTUnwrap(envelope.project.bible)
        XCTAssertFalse(bible.artStyle.isEmpty)
        XCTAssertNotNil(bible.characters.first?.portrait)

        let summaries = try await client.projects()
        let summary = try XCTUnwrap(summaries.first { $0.id == project.id })
        XCTAssertEqual(summary.shots, 3)
        XCTAssertNotNil(summary.cover)

        // Focused edits round-trip and leave other fields alone.
        let shot = envelope.project.shots[0]
        let patched = try await client.patchShot(project.id, shot.id, ShotPatch(action: "a gull lands on the rail", framing: .closeUp))
        let after = try XCTUnwrap(patched.project.shots.first { $0.id == shot.id })
        XCTAssertEqual(after.action, "a gull lands on the rail")
        XCTAssertEqual(after.framing, .closeUp)
        XCTAssertEqual(after.image, shot.image)
        let character = bible.characters[0]
        let withCoat = try await client.patchCharacter(project.id, character.id, CharacterPatch(appearance: "silver coat"))
        XCTAssertEqual(withCoat.project.bible?.character(character.id)?.appearance, "silver coat")
        _ = try await client.patchBible(project.id, BiblePatch(artStyle: "woodcut"))

        // A new take of one shot, then files are served.
        let take = try await client.run(.images, project: project.id, StepRequest(only: [shot.id], reroll: true))
        let takeDone = try await client.waitForJob(take.id, every: .milliseconds(200))
        XCTAssertEqual(takeDone.state, .done)
        let retaken = try await client.project(project.id)
        XCTAssertEqual(retaken.project.shots[0].seedOffset, 1)
        let image = try XCTUnwrap(after.image)
        let (data, response) = try await URLSession.shared.data(from: client.fileURL(project: project.id, path: image, version: 2))
        XCTAssertEqual((response as? HTTPURLResponse)?.statusCode, 200)
        XCTAssertGreaterThan(data.count, 1000)

        let exports = try await client.exports(project.id)
        XCTAssertNotNil(exports.comic.pdf)
        XCTAssertFalse(exports.comic.pages.isEmpty)
        XCTAssertNil(exports.animatic.mp4)

        let jobs = try await client.jobs(project: project.id)
        XCTAssertEqual(jobs.map(\.id), [job.id, take.id])

        // Video settings: project-wide, per shot and per run, then a clip with its seed recorded.
        let settings = VideoSettings(aspect: .vertical, clipSeconds: 1, camera: .orbit, negativePrompt: "blur")
        let configured = try await client.patchSettings(project.id, SettingsPatch(video: settings, animatic: AnimaticSettings(crossfade: 0.25)))
        XCTAssertEqual(configured.project.video, settings)
        XCTAssertEqual(configured.project.animatic.crossfade, 0.25)
        let options = ShotVideoOptions(camera: .static, seed: 7, motion: "the gull takes off")
        let withOptions = try await client.patchShot(project.id, shot.id, ShotPatch(videoOptions: options))
        XCTAssertEqual(withOptions.project.shots[0].videoOptions, options)
        let clip = try await client.run(.video, project: project.id, StepRequest(only: [shot.id], video: VideoOverride(steps: 4)))
        let clipDone = try await client.waitForJob(clip.id, every: .milliseconds(200))
        XCTAssertEqual(clipDone.state, .done, clipDone.error ?? "")
        let animated = try await client.project(project.id).project.shots[0]
        XCTAssertNotNil(animated.video)
        XCTAssertEqual(animated.videoSeed, 7)

        // Errors carry the engine's message.
        do {
            _ = try await client.patchShot(project.id, "nope", ShotPatch(action: "x"))
            XCTFail("expected 404")
        } catch let error as EngineError {
            XCTAssertEqual(error.status, 404)
            XCTAssertTrue(error.message.contains("nope"))
        }

        try await client.deleteProject(project.id)
        let remaining = try await client.projects()
        XCTAssertFalse(remaining.contains { $0.id == project.id })
    }

    func testPortConflictFailsFastWithAnExplanation() async throws {
        // `engine` from setUp already holds its port; a second engine on it must fail fast.
        let second = EngineProcess(configuration: .init(
            engineDirectory: engine.configuration.engineDirectory, port: engine.configuration.port, profile: "mock",
            environment: ["GRIZZLY_HOME": home.path]
        ))
        try second.start()
        let started = ContinuousClock.now
        // A client that cannot reach anything, so only the exit check can end the wait.
        let unreachable = EngineClient(port: 1)
        do {
            _ = try await waitForEngine(unreachable, process: second, timeout: .seconds(60))
            XCTFail("expected a port conflict")
        } catch let error as EngineProcess.LaunchError {
            XCTAssertEqual(error, .portInUse(engine.configuration.port))
            XCTAssertTrue(error.localizedDescription.contains("lsof"))
        }
        XCTAssertLessThan(ContinuousClock.now - started, .seconds(30))
        second.stop()
    }

    func testMissingEngineIsReported() {
        let process = EngineProcess(configuration: .init(engineDirectory: URL(fileURLWithPath: "/nonexistent")))
        XCTAssertThrowsError(try process.start()) { error in
            XCTAssertTrue(error.localizedDescription.contains("No engine at"))
        }
    }
}
