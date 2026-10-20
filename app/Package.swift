// swift-tools-version: 6.0
import PackageDescription

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
        .executableTarget(name: "Grizzly", dependencies: ["GrizzlyCore"]),
        .testTarget(name: "GrizzlyCoreTests", dependencies: ["GrizzlyCore"]),
    ],
    swiftLanguageModes: [.v5]
)
