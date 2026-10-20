import Foundation

// Mirrors grizzly/models.py and the engine's JSON. Keys are snake_case on the
// wire; EngineClient converts them.

public enum StoryFormat: String, Codable, CaseIterable, Identifiable, Sendable {
    case comic, vn, film

    public var id: String { rawValue }

    public var title: String {
        switch self {
        case .comic: "Comic"
        case .vn: "Visual Novel"
        case .film: "Short Film"
        }
    }
}

public enum Framing: String, Codable, CaseIterable, Identifiable, Sendable {
    case wide, medium
    case closeUp = "close-up"

    public var id: String { rawValue }

    public var title: String {
        switch self {
        case .wide: "Wide"
        case .medium: "Medium"
        case .closeUp: "Close-up"
        }
    }
}

public struct DialogueLine: Codable, Hashable, Sendable {
    public var speaker: String
    public var text: String

    public init(speaker: String, text: String) {
        self.speaker = speaker
        self.text = text
    }
}

public struct Character: Codable, Identifiable, Hashable, Sendable {
    public var id: String
    public var name: String
    public var role: String
    public var personality: String
    public var appearance: String
    public var voice: String
    public var portrait: String?
    public var portraitSeed: Int
}

public struct Location: Codable, Identifiable, Hashable, Sendable {
    public var id: String
    public var name: String
    public var description: String
}

public struct StoryBible: Codable, Hashable, Sendable {
    public var title: String
    public var logline: String
    public var genre: String
    public var tone: String
    public var artStyle: String
    public var characters: [Character]
    public var locations: [Location]

    public func character(_ id: String) -> Character? { characters.first { $0.id == id } }
    public func location(_ id: String) -> Location? { locations.first { $0.id == id } }
}

public struct SceneOutline: Codable, Identifiable, Hashable, Sendable {
    public var id: String
    public var title: String
    public var summary: String
    public var locationId: String
    public var characterIds: [String]
}

public struct Outline: Codable, Hashable, Sendable {
    public var scenes: [SceneOutline]
}

public struct Shot: Codable, Identifiable, Hashable, Sendable {
    public var id: String
    public var sceneId: String
    public var framing: Framing
    public var action: String
    public var characterIds: [String]
    public var locationId: String
    public var dialogue: [DialogueLine]
    public var narration: String
    public var duration: Double
    public var image: String?
    public var seedOffset: Int
    public var video: String?
    public var videoTake: Int
}

public struct Project: Codable, Identifiable, Hashable, Sendable {
    public var id: String
    public var title: String
    public var premise: String
    public var format: StoryFormat
    public var seed: Int
    public var created: String
    public var bible: StoryBible?
    public var outline: Outline?
    public var shots: [Shot]

    public func shots(inScene id: String) -> [Shot] { shots.filter { $0.sceneId == id } }
}

public struct ProjectStatus: Codable, Hashable, Sendable {
    public var bible: Bool
    public var outline: Bool
    public var shots: Bool
    public var portraits: Bool
    public var images: Bool
}

/// A project as returned by GET /api/projects/{id} and the edit endpoints.
public struct ProjectEnvelope: Codable, Hashable, Sendable {
    public var project: Project
    public var status: ProjectStatus
    public var busy: Bool
}

public struct ProjectSummary: Codable, Identifiable, Hashable, Sendable {
    public var id: String
    public var title: String
    public var format: StoryFormat
    public var created: String
    public var logline: String
    public var cover: String?
    public var shots: Int
    public var status: ProjectStatus
    public var busy: Bool
}

public enum JobState: String, Codable, Sendable {
    case queued, running, done, failed

    public var isFinished: Bool { self == .done || self == .failed }
}

public struct Job: Codable, Identifiable, Hashable, Sendable {
    public var id: String
    public var project: String
    public var step: String
    /// The step currently running; for "all" this moves bible -> ... -> export.
    public var stage: String?
    public var state: JobState
    public var progress: String
    public var result: String?
    public var error: String?
    public var created: Double?
    public var finished: Double?

    /// Which of the app's four pipeline stages this job is in (0...3).
    public var stageIndex: Int? {
        switch stage ?? step {
        case "bible", "outline", "shots": 0
        case "portraits": 1
        case "images", "video": 2
        case "comic", "vn", "animatic": 3
        default: nil
        }
    }

    /// Parses progress like "3/16 shot s1_03" into (3, 16) for progress bars.
    public var fraction: (done: Int, total: Int)? {
        let head = progress.split(separator: " ").first ?? ""
        let parts = head.split(separator: "/")
        guard parts.count == 2, let done = Int(parts[0]), let total = Int(parts[1]), total > 0 else { return nil }
        return (done, total)
    }

    /// Progress text without the "3/16" counter.
    public var progressLabel: String {
        fraction == nil ? progress : progress.split(separator: " ").dropFirst().joined(separator: " ")
    }
}

public struct Exports: Codable, Hashable, Sendable {
    public struct Comic: Codable, Hashable, Sendable {
        public var pdf: String?
        public var pages: [String]
    }

    public struct VisualNovel: Codable, Hashable, Sendable {
        public var html: String?
        public var renpy: String?
    }

    public struct Animatic: Codable, Hashable, Sendable {
        public var mp4: String?
    }

    public var comic: Comic
    public var vn: VisualNovel
    public var animatic: Animatic
}

public struct EngineInfo: Codable, Hashable, Sendable {
    public var profile: String
    public var llm: String
    public var image: String
    public var ref: String
    public var video: String
    public var steps: [String]
    public var projectsDir: String
}

public struct Health: Codable, Hashable, Sendable {
    public var ok: Bool
    public var version: String
    public var profile: String
}

public enum PipelineStep: String, Sendable, CaseIterable {
    case all, bible, outline, shots, portraits, images, video, comic, vn, animatic
}

public struct StepRequest: Encodable, Sendable {
    public var force = false
    public var only: [String]?
    public var scenes = 4
    public var shots = 4
    public var characters: Int?
    public var locations = 3
    public var reroll = false

    public init(force: Bool = false, only: [String]? = nil, scenes: Int = 4, shots: Int = 4, reroll: Bool = false) {
        self.force = force
        self.only = only
        self.scenes = scenes
        self.shots = shots
        self.reroll = reroll
    }
}

public struct BiblePatch: Encodable, Sendable {
    public var title: String?
    public var logline: String?
    public var tone: String?
    public var artStyle: String?

    public init(title: String? = nil, logline: String? = nil, tone: String? = nil, artStyle: String? = nil) {
        self.title = title
        self.logline = logline
        self.tone = tone
        self.artStyle = artStyle
    }
}

public struct CharacterPatch: Encodable, Sendable {
    public var name: String?
    public var personality: String?
    public var appearance: String?
    public var voice: String?

    public init(name: String? = nil, personality: String? = nil, appearance: String? = nil, voice: String? = nil) {
        self.name = name
        self.personality = personality
        self.appearance = appearance
        self.voice = voice
    }
}

public struct ShotPatch: Encodable, Sendable {
    public var action: String?
    public var framing: Framing?
    public var narration: String?
    public var dialogue: [DialogueLine]?
    public var duration: Double?

    public init(action: String? = nil, framing: Framing? = nil, narration: String? = nil, dialogue: [DialogueLine]? = nil, duration: Double? = nil) {
        self.action = action
        self.framing = framing
        self.narration = narration
        self.dialogue = dialogue
        self.duration = duration
    }
}
