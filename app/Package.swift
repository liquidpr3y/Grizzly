// swift-tools-version: 6.0
import Foundation
import PackageDescription

// Embedded into the executable so `swift run` / Xcode runs get the app's name
// and are allowed to reach the local engine over HTTP (App Transport Security).
let infoPlist = URL(fileURLWithPath: #filePath).deletingLastPathComponent().appendingPathComponent("Support/Info.plist").path

let package = Package(
    name: "Grizzly",
    platforms: [.macOS(.v14)],
    products: [
        .executable(name: "Grizzly", targets: ["Grizzly"]),
    ],
    targets: [
        // Engine client, models and process management. Foundation only, so it
        // also builds and is tested on Linux against the real Python engine.
        .target(name: "GrizzlyCore"),
        // The SwiftUI app. macOS only; on other platforms it builds to a stub.
        .executableTarget(
            name: "Grizzly",
            dependencies: ["GrizzlyCore"],
            linkerSettings: [
                .unsafeFlags(["-Xlinker", "-sectcreate", "-Xlinker", "__TEXT", "-Xlinker", "__info_plist", "-Xlinker", infoPlist],
                             .when(platforms: [.macOS])),
            ]
        ),
        .testTarget(name: "GrizzlyCoreTests", dependencies: ["GrizzlyCore"]),
    ],
    swiftLanguageModes: [.v5]
)
