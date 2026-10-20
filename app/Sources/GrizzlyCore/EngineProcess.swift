import Foundation

/// Launches and supervises the Python engine (`grizzly serve`) from a local
/// checkout with a `.venv`. This is the development setup; a shipped app
/// would bundle the engine inside the .app and point `engineDirectory` there.
public final class EngineProcess: @unchecked Sendable {
    public struct Configuration: Sendable {
        public var engineDirectory: URL
        public var port: Int
        public var profile: String?
        public var environment: [String: String]

        public init(engineDirectory: URL, port: Int = 8642, profile: String? = nil, environment: [String: String] = [:]) {
            self.engineDirectory = engineDirectory
            self.port = port
            self.profile = profile
            self.environment = environment
        }

        /// The engine executable inside the checkout's virtual environment.
        public var executable: URL {
            engineDirectory.appendingPathComponent(".venv/bin/grizzly")
        }
    }

    public enum LaunchError: LocalizedError, Equatable {
        case missingExecutable(URL)
        /// Something else is listening on the port, usually an engine left
        /// running by an earlier session.
        case portInUse(Int)
        /// The engine quit while starting; carries its last output.
        case exited(status: Int32, output: String)

        public var errorDescription: String? {
            switch self {
            case let .missingExecutable(url):
                "No engine at \(url.path). Choose the Grizzly folder that contains the .venv you installed with uv."
            case let .portInUse(port):
                "Port \(port) is already in use, most likely by a Grizzly engine left running from an earlier session "
                    + "(for example after stopping the app from Xcode). Find it with `lsof -nP -iTCP:\(port) -sTCP:LISTEN`, "
                    + "quit it with `kill <PID>`, then try again, or choose another port in Settings."
            case let .exited(status, output):
                "The engine stopped while starting (exit code \(status)).\n\n\(output)"
            }
        }
    }

    public let configuration: Configuration
    /// Called with each line the engine prints (on a background queue).
    public var onOutput: ((String) -> Void)?
    private var process: Process?
    private var recent: [String] = []
    private let lock = NSLock()

    public init(configuration: Configuration) {
        self.configuration = configuration
    }

    public var isRunning: Bool {
        lock.lock()
        defer { lock.unlock() }
        return process?.isRunning ?? false
    }

    public func start() throws {
        guard FileManager.default.isExecutableFile(atPath: configuration.executable.path) else {
            throw LaunchError.missingExecutable(configuration.executable)
        }
        let process = Process()
        process.executableURL = configuration.executable
        // --exit-with-parent: if this app is killed outright (no chance to call
        // stop()), the engine notices and exits instead of lingering.
        process.arguments = (configuration.profile.map { ["--profile", $0] } ?? [])
            + ["serve", "--port", String(configuration.port), "--exit-with-parent"]
        process.currentDirectoryURL = configuration.engineDirectory
        process.environment = Self.environment(adding: configuration.environment)

        let pipe = Pipe()
        process.standardOutput = pipe
        process.standardError = pipe
        pipe.fileHandleForReading.readabilityHandler = { [weak self] handle in
            let data = handle.availableData
            guard !data.isEmpty, let text = String(data: data, encoding: .utf8) else { return }
            for line in text.split(whereSeparator: \.isNewline) {
                self?.remember(String(line))
                self?.onOutput?(String(line))
            }
        }
        try process.run()
        lock.lock()
        self.process = process
        lock.unlock()
    }

    /// Set once the process has exited: why it stopped.
    public var exitError: LaunchError? {
        lock.lock()
        defer { lock.unlock() }
        guard let process, !process.isRunning else { return nil }
        let output = recent.joined(separator: "\n")
        if output.contains("PORT_IN_USE") || output.contains("address already in use") {
            return .portInUse(configuration.port)
        }
        return .exited(status: process.terminationStatus, output: recent.suffix(12).joined(separator: "\n"))
    }

    private func remember(_ line: String) {
        lock.lock()
        recent.append(line)
        if recent.count > 50 { recent.removeFirst(recent.count - 50) }
        lock.unlock()
    }

    public func stop() {
        lock.lock()
        let process = self.process
        self.process = nil
        lock.unlock()
        guard let process, process.isRunning else { return }
        (process.standardOutput as? Pipe)?.fileHandleForReading.readabilityHandler = nil
        process.terminate()
        // Give the engine a moment to shut down cleanly, then make sure: a
        // leftover engine would keep gigabytes of model weights resident.
        let deadline = Date().addingTimeInterval(5)
        while process.isRunning && Date() < deadline {
            Thread.sleep(forTimeInterval: 0.1)
        }
        if process.isRunning {
            kill(process.processIdentifier, SIGKILL)
        }
    }

    /// Apps launched from Finder get a minimal PATH; the engine needs ffmpeg
    /// (Homebrew) and the user's tools.
    static func environment(adding extra: [String: String]) -> [String: String] {
        var env = ProcessInfo.processInfo.environment
        let home = FileManager.default.homeDirectoryForCurrentUser.path
        let paths = ["/opt/homebrew/bin", "/usr/local/bin", "\(home)/.local/bin", "/usr/bin", "/bin", "/usr/sbin", "/sbin"]
        let existing = env["PATH"].map { $0.split(separator: ":").map(String.init) } ?? []
        env["PATH"] = (paths + existing).reduce(into: [String]()) { if !$0.contains($1) { $0.append($1) } }.joined(separator: ":")
        env["PYTHONUNBUFFERED"] = "1"
        for (key, value) in extra { env[key] = value }
        return env
    }
}

/// Waits until the engine answers its health check. With `process`, fails as
/// soon as the engine exits instead of waiting out the timeout.
public func waitForEngine(_ client: EngineClient, process: EngineProcess? = nil, timeout: Duration = .seconds(60)) async throws -> Health {
    let clock = ContinuousClock()
    let deadline = clock.now.advanced(by: timeout)
    var lastError: Error?
    while clock.now < deadline {
        do {
            return try await client.health()
        } catch {
            lastError = error
            if let exit = process?.exitError { throw exit }
            try await Task.sleep(for: .milliseconds(500))
        }
    }
    throw lastError ?? EngineError(status: 0, message: "Engine did not start")
}
