import Foundation

/// First-launch state from `GET /api/setup`: the hardware check and the
/// models the active profile needs.
public struct SetupStatus: Codable, Hashable, Sendable {
    public var profile: String
    public var system: SystemInfo
    public var models: [ModelStatus]
    public var notes: [String]
    public var ready: Bool
    public var downloading: Bool
    public var cacheDir: String

    public var required: [ModelStatus] { models.filter(\.required) }
    public var optional: [ModelStatus] { models.filter { !$0.required } }

    /// Bytes still to fetch for the given models (default: the required ones).
    public func remainingBytes(_ ids: Set<String>? = nil) -> Int64 {
        models
            .filter { model in !model.complete && (ids?.contains(model.id) ?? model.required) }
            .reduce(0) { $0 + $1.remainingBytes }
    }

    /// Overall download progress across the required models, 0...1.
    public var requiredFraction: Double {
        let total = required.reduce(Int64(0)) { $0 + $1.sizeBytes }
        guard total > 0 else { return ready ? 1 : 0 }
        return Double(required.reduce(Int64(0)) { $0 + $1.downloadedBytes }) / Double(total)
    }
}

public struct SystemInfo: Codable, Hashable, Sendable {
    public struct Check: Codable, Hashable, Sendable, Identifiable {
        public enum Status: String, Codable, Sendable { case ok, warn, fail }
        public var id: String
        public var label: String
        public var status: Status
        public var detail: String
    }

    public var chip: String
    public var arch: String
    public var macos: String
    public var memoryBytes: Int64
    public var diskFreeBytes: Int64
    public var checks: [Check]
    public var recommendedProfile: String
    public var supported: Bool
}

public struct ModelStatus: Codable, Hashable, Sendable, Identifiable {
    public enum State: String, Codable, Sendable { case idle, queued, downloading, done, failed }

    public var id: String
    public var title: String
    public var repo: String
    public var purpose: String
    public var required: Bool
    public var license: String
    public var sizeBytes: Int64
    public var downloadedBytes: Int64
    public var complete: Bool
    public var state: State
    public var error: String?

    public var remainingBytes: Int64 { complete ? 0 : max(0, sizeBytes - downloadedBytes) }
    public var fraction: Double { sizeBytes > 0 ? min(1, Double(downloadedBytes) / Double(sizeBytes)) : (complete ? 1 : 0) }
    public var isActive: Bool { state == .queued || state == .downloading }
}

public struct DownloadRequest: Encodable, Sendable {
    /// nil: every required model that isn't downloaded yet.
    public var models: [String]?

    public init(models: [String]? = nil) {
        self.models = models
    }
}

/// "5.9 GB", "350 MB".
public func formatBytes(_ bytes: Int64) -> String {
    let gb = Double(bytes) / 1_000_000_000
    if gb >= 1 { return String(format: "%.1f GB", gb) }
    return String(format: "%.0f MB", Double(bytes) / 1_000_000)
}
