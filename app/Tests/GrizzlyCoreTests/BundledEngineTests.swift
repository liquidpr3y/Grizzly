import Foundation
#if canImport(FoundationNetworking)
import FoundationNetworking
#endif
import XCTest
@testable import GrizzlyCore

final class EngineLayoutTests: XCTestCase {
    func testLayoutIsDetectedFromTheFolder() throws {
        let dir = FileManager.default.temporaryDirectory.appendingPathComponent("grizzly-layout-\(UUID().uuidString)")
        defer { try? FileManager.default.removeItem(at: dir) }
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)

        var config = EngineProcess.Configuration(engineDirectory: dir, port: 9000, profile: "mock")
        XCTAssertEqual(config.layout, .checkout)
        XCTAssertEqual(config.executable.lastPathComponent, "grizzly")
        XCTAssertEqual(config.arguments.first, "--profile")
        XCTAssertTrue(config.layoutEnvironment.isEmpty)

        let python = dir.appendingPathComponent("python/bin/python3")
        try FileManager.default.createDirectory(at: python.deletingLastPathComponent(), withIntermediateDirectories: true)
        _ = FileManager.default.createFile(atPath: python.path, contents: Data("#!/bin/sh\n".utf8), attributes: [.posixPermissions: 0o755])
        config = EngineProcess.Configuration(engineDirectory: dir, port: 9000, profile: nil)
        XCTAssertEqual(config.layout, .bundled)
        XCTAssertEqual(config.executable, python)
        XCTAssertEqual(config.arguments, ["-s", "-m", "grizzly", "serve", "--port", "9000", "--exit-with-parent"])
        XCTAssertEqual(config.layoutEnvironment["PYTHONDONTWRITEBYTECODE"], "1")
        XCTAssertFalse(config.layoutEnvironment["NUMBA_CACHE_DIR"]!.hasPrefix(dir.path), "caches must live outside the bundle")

        let env = EngineProcess.environment(adding: config.layoutEnvironment.merging(["PYTHONPATH": "/x"]) { $1 }, layout: .bundled)
        XCTAssertTrue(env["PATH"]!.hasPrefix(dir.appendingPathComponent("bin").path + ":"))
        XCTAssertEqual(env["PYTHONPATH"], "/x", "explicit overrides still win")
        XCTAssertNil(EngineProcess.environment(adding: [:], layout: .bundled)["VIRTUAL_ENV"])
    }
}

/// Runs a story through an engine built by scripts/bundle-engine.sh, the way
/// the shipped app does: standalone Python, no .venv, its own ffmpeg.
/// Set GRIZZLY_BUNDLED_ENGINE to the built engine folder.
final class BundledEngineTests: XCTestCase {
    func testBundledEngineRunsAStoryAndStaysUntouched() async throws {
        guard let dir = ProcessInfo.processInfo.environment["GRIZZLY_BUNDLED_ENGINE"] else {
            throw XCTSkip("Set GRIZZLY_BUNDLED_ENGINE to a folder built by scripts/bundle-engine.sh")
        }
        let engineDir = URL(fileURLWithPath: dir)
        let home = FileManager.default.temporaryDirectory.appendingPathComponent("grizzly-bundled-\(UUID().uuidString)")
        defer { try? FileManager.default.removeItem(at: home) }
        let before = try snapshot(engineDir)

        let port = Int.random(in: 20000..<40000)
        let engine = EngineProcess(configuration: .init(
            engineDirectory: engineDir, port: port, profile: "mock", environment: ["GRIZZLY_HOME": home.path]
        ))
        XCTAssertEqual(engine.configuration.layout, .bundled)
        try engine.start()
        defer { engine.stop() }
        let client = EngineClient(port: port)
        _ = try await waitForEngine(client, process: engine, timeout: .seconds(60))

        // A film exercises ffmpeg end to end: animatic clips, concat, subtitles.
        let project = try await client.createProject(title: "Bundled", premise: "A keeper hears the sea.", format: .film)
        let job = try await client.run(.all, project: project.id, StepRequest(scenes: 1, shots: 2))
        let done = try await client.waitForJob(job.id, every: .milliseconds(200))
        XCTAssertEqual(done.state, .done, done.error ?? "")
        let exports = try await client.exports(project.id)
        XCTAssertNotNil(exports.animatic.mp4)

        XCTAssertEqual(try snapshot(engineDir), before, "the engine wrote into its own (signed, read-only) folder")
    }

    /// Every file path and size under `root`.
    private func snapshot(_ root: URL) throws -> [String: Int] {
        var out: [String: Int] = [:]
        let keys: [URLResourceKey] = [.fileSizeKey, .isRegularFileKey]
        let walker = FileManager.default.enumerator(at: root, includingPropertiesForKeys: keys)!
        for case let url as URL in walker {
            let values = try url.resourceValues(forKeys: Set(keys))
            if values.isRegularFile == true { out[url.path] = values.fileSize ?? 0 }
        }
        return out
    }
}
