import Foundation
#if canImport(FoundationNetworking)
import FoundationNetworking
#endif

public struct EngineError: LocalizedError, Sendable {
    public var status: Int
    public var message: String

    public var errorDescription: String? { message }
}

/// FastAPI's error body: {"detail": "..."}.
private struct ErrorDetail: Decodable {
    var detail: String
}

/// Talks to the Python engine's local HTTP API (grizzly/server.py).
public final class EngineClient: @unchecked Sendable {
    public let baseURL: URL
    private let session: URLSession
    private let decoder: JSONDecoder
    private let encoder: JSONEncoder

    public init(baseURL: URL, session: URLSession = .shared) {
        self.baseURL = baseURL
        self.session = session
        decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        encoder = JSONEncoder()
        encoder.keyEncodingStrategy = .convertToSnakeCase
    }

    public convenience init(port: Int) {
        self.init(baseURL: URL(string: "http://127.0.0.1:\(port)")!)
    }

    // MARK: Engine

    public func health() async throws -> Health { try await get("/api/health") }
    public func info() async throws -> EngineInfo { try await get("/api/info") }

    // MARK: Projects

    public func projects() async throws -> [ProjectSummary] { try await get("/api/projects") }

    public func project(_ id: String) async throws -> ProjectEnvelope { try await get("/api/projects/\(id)") }

    public func createProject(title: String, premise: String, format: StoryFormat) async throws -> Project {
        struct Body: Encodable { var title: String; var premise: String; var format: StoryFormat }
        return try await send("POST", "/api/projects", body: Body(title: title, premise: premise, format: format))
    }

    public func deleteProject(_ id: String) async throws {
        struct Deleted: Decodable { var deleted: String }
        let _: Deleted = try await send("DELETE", "/api/projects/\(id)", body: Optional<String>.none)
    }

    public func patchBible(_ project: String, _ patch: BiblePatch) async throws -> ProjectEnvelope {
        try await send("PATCH", "/api/projects/\(project)/bible", body: patch)
    }

    public func patchCharacter(_ project: String, _ character: String, _ patch: CharacterPatch) async throws -> ProjectEnvelope {
        try await send("PATCH", "/api/projects/\(project)/characters/\(character)", body: patch)
    }

    public func patchShot(_ project: String, _ shot: String, _ patch: ShotPatch) async throws -> ProjectEnvelope {
        try await send("PATCH", "/api/projects/\(project)/shots/\(shot)", body: patch)
    }

    public func patchSettings(_ project: String, _ patch: SettingsPatch) async throws -> ProjectEnvelope {
        try await send("PATCH", "/api/projects/\(project)/settings", body: patch)
    }

    public func exports(_ project: String) async throws -> Exports { try await get("/api/projects/\(project)/exports") }

    // MARK: Jobs

    public func run(_ step: PipelineStep, project: String, _ request: StepRequest = StepRequest()) async throws -> Job {
        try await send("POST", "/api/projects/\(project)/steps/\(step.rawValue)", body: request)
    }

    public func job(_ id: String) async throws -> Job { try await get("/api/jobs/\(id)") }

    public func jobs(project: String) async throws -> [Job] {
        try await get("/api/jobs", query: [URLQueryItem(name: "project", value: project)])
    }

    /// Polls a job until it finishes, reporting each update.
    public func waitForJob(_ id: String, every interval: Duration = .seconds(1), onUpdate: (Job) -> Void = { _ in }) async throws -> Job {
        while true {
            let current = try await job(id)
            onUpdate(current)
            if current.state.isFinished { return current }
            try await Task.sleep(for: interval)
        }
    }

    // MARK: Files

    /// URL of a project file (image, clip, export). `version` busts caches
    /// after a re-render, since paths stay the same.
    public func fileURL(project: String, path: String, version: Int = 0) -> URL {
        var components = URLComponents(url: baseURL.appendingPathComponent("files/\(project)/\(path)"), resolvingAgainstBaseURL: false)!
        if version > 0 { components.queryItems = [URLQueryItem(name: "v", value: String(version))] }
        return components.url!
    }

    // MARK: Plumbing

    private func get<T: Decodable>(_ path: String, query: [URLQueryItem] = []) async throws -> T {
        try await send("GET", path, body: Optional<String>.none, query: query)
    }

    private func send<T: Decodable, B: Encodable>(_ method: String, _ path: String, body: B?, query: [URLQueryItem] = []) async throws -> T {
        var components = URLComponents(url: baseURL.appendingPathComponent(path), resolvingAgainstBaseURL: false)!
        if !query.isEmpty { components.queryItems = query }
        var request = URLRequest(url: components.url!)
        request.httpMethod = method
        request.timeoutInterval = 30
        if let body {
            request.httpBody = try encoder.encode(body)
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        }
        let (data, response) = try await session.data(for: request)
        let status = (response as? HTTPURLResponse)?.statusCode ?? 0
        guard (200..<300).contains(status) else {
            let message = (try? decoder.decode(ErrorDetail.self, from: data).detail)
                ?? String(data: data, encoding: .utf8) ?? "HTTP \(status)"
            throw EngineError(status: status, message: message)
        }
        return try decoder.decode(T.self, from: data)
    }
}
