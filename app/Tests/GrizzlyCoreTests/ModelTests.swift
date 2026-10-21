import Foundation
import XCTest
@testable import GrizzlyCore

final class ModelTests: XCTestCase {
    func testJobProgressParsing() {
        var job = Job(id: "j", project: "p", step: "all", stage: "images", state: .running, progress: "3/16 shot s1_03",
                      result: nil, error: nil, created: nil, finished: nil)
        XCTAssertEqual(job.fraction?.done, 3)
        XCTAssertEqual(job.fraction?.total, 16)
        XCTAssertEqual(job.progressLabel, "shot s1_03")
        XCTAssertEqual(job.stageIndex, 2)
        job.progress = "images"
        XCTAssertNil(job.fraction)
        XCTAssertEqual(job.progressLabel, "images")
    }

    func testPatchesEncodeSnakeCaseAndOmitUnsetFields() throws {
        let encoder = JSONEncoder()
        encoder.keyEncodingStrategy = .convertToSnakeCase
        encoder.outputFormatting = .sortedKeys
        let bible = String(decoding: try encoder.encode(BiblePatch(artStyle: "ink")), as: UTF8.self)
        XCTAssertEqual(bible, #"{"art_style":"ink"}"#)
        let shot = String(decoding: try encoder.encode(ShotPatch(framing: .closeUp)), as: UTF8.self)
        XCTAssertEqual(shot, #"{"framing":"close-up"}"#)
    }

    func testVideoSettingsRoundTripAndFrameCounts() throws {
        let encoder = JSONEncoder()
        encoder.keyEncodingStrategy = .convertToSnakeCase
        encoder.outputFormatting = .sortedKeys
        let request = StepRequest(only: ["s1"], video: VideoOverride(quality: .draft, steps: 8))
        let json = String(decoding: try encoder.encode(request), as: UTF8.self)
        XCTAssertTrue(json.contains(#""video":{"quality":"draft","steps":8}"#), json)
        let patch = String(decoding: try encoder.encode(SettingsPatch(video: VideoSettings(aspect: .vertical, clipSeconds: 3))), as: UTF8.self)
        XCTAssertEqual(patch, #"{"video":{"aspect":"9:16","clip_seconds":3}}"#)

        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        let wire = #"{"aspect":"2.39:1","quality":null,"clip_seconds":2.5,"steps":null}"#
        let settings = try decoder.decode(VideoSettings.self, from: Data(wire.utf8))
        XCTAssertEqual(settings, VideoSettings(aspect: .scope, clipSeconds: 2.5))

        // Same as grizzly/video_settings.py frames_for.
        XCTAssertEqual(VideoSettings.frames(forSeconds: 1.7), 41)
        XCTAssertEqual(VideoSettings.frames(forSeconds: 3), 73)
        XCTAssertEqual(VideoSettings.frames(forSeconds: 0.1), 17)
        XCTAssertEqual(VideoSettings.frames(forSeconds: 30), 121)
    }

    func testFileURLsAreCacheBusted() {
        let client = EngineClient(port: 8642)
        XCTAssertEqual(client.fileURL(project: "p", path: "images/shots/s1_01.png").absoluteString,
                       "http://127.0.0.1:8642/files/p/images/shots/s1_01.png")
        XCTAssertEqual(client.fileURL(project: "p", path: "a.png", version: 3).absoluteString,
                       "http://127.0.0.1:8642/files/p/a.png?v=3")
    }

    func testEnginePathIncludesHomebrew() {
        let env = EngineProcess.environment(adding: ["X": "1"])
        XCTAssertTrue(env["PATH"]!.hasPrefix("/opt/homebrew/bin:"))
        XCTAssertEqual(env["X"], "1")
        XCTAssertEqual(env["PYTHONUNBUFFERED"], "1")
    }
}
