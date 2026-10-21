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

/// Frame shape for clips, film and visual novel panels, and the animatic.
public enum VideoAspect: String, Codable, CaseIterable, Identifiable, Sendable {
    case widescreen = "16:9"
    case vertical = "9:16"
    case square = "1:1"
    case classic = "4:3"
    case scope = "2.39:1"

    public var id: String { rawValue }

    /// Width over height.
    public var ratio: Double {
        switch self {
        case .widescreen: 16 / 9
        case .vertical: 9 / 16
        case .square: 1
        case .classic: 4 / 3
        case .scope: 2.39
        }
    }

    public var title: String {
        switch self {
        case .widescreen: "16:9 Widescreen"
        case .vertical: "9:16 Vertical"
        case .square: "1:1 Square"
        case .classic: "4:3 Classic"
        case .scope: "2.39:1 Cinemascope"
        }
    }
}

public enum VideoQuality: String, Codable, CaseIterable, Identifiable, Sendable {
    case draft, standard

    public var id: String { rawValue }

    public var title: String {
        switch self {
        case .draft: "Draft (480p, about 2x faster)"
        case .standard: "Standard (720p)"
        }
    }
}

/// How the camera moves in a clip. `.auto` picks a gentle move from the framing.
public enum CameraMove: String, Codable, CaseIterable, Identifiable, Sendable {
    case auto, `static`
    case pushIn = "push-in"
    case pullOut = "pull-out"
    case panLeft = "pan-left"
    case panRight = "pan-right"
    case tiltUp = "tilt-up"
    case tiltDown = "tilt-down"
    case orbit, tracking, handheld
    case craneUp = "crane-up"

    public var id: String { rawValue }

    public var title: String {
        switch self {
        case .auto: "Auto (from framing)"
        case .static: "Static"
        case .pushIn: "Push in"
        case .pullOut: "Pull out"
        case .panLeft: "Pan left"
        case .panRight: "Pan right"
        case .tiltUp: "Tilt up"
        case .tiltDown: "Tilt down"
        case .orbit: "Orbit"
        case .tracking: "Tracking"
        case .handheld: "Handheld"
        case .craneUp: "Crane up"
        }
    }
}

/// Project-wide image-to-video options. nil means the video model's default.
public struct VideoSettings: Codable, Hashable, Sendable {
    public var aspect: VideoAspect = .widescreen
    public var quality: VideoQuality?
    public var clipSeconds: Double?
    public var steps: Int?
    /// How closely clips follow the prompt. 1 turns guidance off: about twice as fast.
    public var guidance: Double?
    public var camera: CameraMove = .auto
    /// Look of the clips; empty uses the story bible's art style.
    public var style = ""
    /// What the clips should avoid; empty uses the video model's own default.
    public var negativePrompt = ""

    public init(aspect: VideoAspect = .widescreen, quality: VideoQuality? = nil, clipSeconds: Double? = nil, steps: Int? = nil,
                guidance: Double? = nil, camera: CameraMove = .auto, style: String = "", negativePrompt: String = "") {
        self.aspect = aspect
        self.quality = quality
        self.clipSeconds = clipSeconds
        self.steps = steps
        self.guidance = guidance
        self.camera = camera
        self.style = style
        self.negativePrompt = negativePrompt
    }

    /// The video model renders at 24fps and needs 4n+1 frames, 17...121.
    /// Mirrors grizzly/video_settings.py `frames_for`.
    public static func frames(forSeconds seconds: Double) -> Int {
        let n = Int((seconds * 24 / 4).rounded(.toNearestOrEven))
        return min(121, max(17, n * 4 + 1))
    }
}

public enum AnimaticResolution: String, Codable, CaseIterable, Identifiable, Sendable {
    case hd = "720p"
    case fullHD = "1080p"

    public var id: String { rawValue }
}

public struct AnimaticSettings: Codable, Hashable, Sendable {
    public var fps = 24
    public var resolution: AnimaticResolution = .hd
    /// Seconds each shot dissolves into the next; 0 is a hard cut.
    public var crossfade = 0.0
    /// Narration and dialogue as a subtitle track in the film.
    public var subtitles = true

    public init(fps: Int = 24, resolution: AnimaticResolution = .hd, crossfade: Double = 0, subtitles: Bool = true) {
        self.fps = fps
        self.resolution = resolution
        self.crossfade = crossfade
        self.subtitles = subtitles
    }
}

/// One run's overrides on top of the project and shot video settings.
public struct VideoOverride: Codable, Hashable, Sendable {
    public var aspect: VideoAspect?
    public var quality: VideoQuality?
    public var clipSeconds: Double?
    public var steps: Int?
    public var seed: Int?
    public var guidance: Double?

    public init(aspect: VideoAspect? = nil, quality: VideoQuality? = nil, clipSeconds: Double? = nil, steps: Int? = nil,
                seed: Int? = nil, guidance: Double? = nil) {
        self.aspect = aspect
        self.quality = quality
        self.clipSeconds = clipSeconds
        self.steps = steps
        self.seed = seed
        self.guidance = guidance
    }
}

/// A shot's own clip settings. nil means the project's setting.
public struct ShotVideoOptions: Codable, Hashable, Sendable {
    public var clipSeconds: Double?
    public var steps: Int?
    public var camera: CameraMove?
    /// Locked seed: every clip of this shot uses it, even on a reroll.
    public var seed: Int?
    /// Extra direction for the motion, e.g. "she turns to the window".
    public var motion = ""

    public init(clipSeconds: Double? = nil, steps: Int? = nil, camera: CameraMove? = nil, seed: Int? = nil, motion: String = "") {
        self.clipSeconds = clipSeconds
        self.steps = steps
        self.camera = camera
        self.seed = seed
        self.motion = motion
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

/// Named StoryCharacter to avoid clashing with Swift.Character.
public struct StoryCharacter: Codable, Identifiable, Hashable, Sendable {
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
    public var characters: [StoryCharacter]
    public var locations: [Location]

    public func character(_ id: String) -> StoryCharacter? { characters.first { $0.id == id } }
    public func location(_ id: String) -> Location? { locations.first { $0.id == id } }
}

public struct SceneOutline: Codable, Identifiable, Hashable, Sendable {
    public var id: String
    public var title: String
    public var summary: String
    public var locationId: String
    public var characterIds: [String]

    public init(id: String, title: String, summary: String, locationId: String, characterIds: [String]) {
        self.id = id
        self.title = title
        self.summary = summary
        self.locationId = locationId
        self.characterIds = characterIds
    }
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
    /// Seed the current clip was made with.
    public var videoSeed: Int?
    public var videoOptions: ShotVideoOptions
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
    public var video: VideoSettings
    public var animatic: AnimaticSettings

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
    /// Video step only: overrides the project and shot video settings for this run.
    public var video: VideoOverride?

    public init(force: Bool = false, only: [String]? = nil, scenes: Int = 4, shots: Int = 4, reroll: Bool = false, video: VideoOverride? = nil) {
        self.force = force
        self.only = only
        self.scenes = scenes
        self.shots = shots
        self.reroll = reroll
        self.video = video
    }
}

public struct SettingsPatch: Encodable, Sendable {
    public var video: VideoSettings?
    public var animatic: AnimaticSettings?

    public init(video: VideoSettings? = nil, animatic: AnimaticSettings? = nil) {
        self.video = video
        self.animatic = animatic
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
    public var videoOptions: ShotVideoOptions?

    public init(action: String? = nil, framing: Framing? = nil, narration: String? = nil, dialogue: [DialogueLine]? = nil,
                duration: Double? = nil, videoOptions: ShotVideoOptions? = nil) {
        self.action = action
        self.framing = framing
        self.narration = narration
        self.dialogue = dialogue
        self.duration = duration
        self.videoOptions = videoOptions
    }
}
