#if os(macOS)
import AVKit  // the macOS 27 SDK's AVKit has its own `State`, hence `@SwiftUI.State` below
import GrizzlyCore
import Observation
import SwiftUI

struct StoryboardTab: View {
    @Environment(AppModel.self) private var model
    var project: Project
    @SwiftUI.State private var selectedShot: String?

    var body: some View {
        if project.shots.isEmpty {
            ContentUnavailableView {
                Label("No storyboard yet", systemImage: "rectangle.split.3x3")
            } description: {
                Text("Write the story to get a shot list, then draw the panels.")
            } actions: {
                Button("Write Story") { model.run(.all, StepRequest()) }
                    .buttonStyle(.borderedProminent)
                    .disabled(model.isBusy(project.id))
            }
        } else {
            ScrollView {
                LazyVStack(alignment: .leading, spacing: 30) {
                    ForEach(Array(scenes.enumerated()), id: \.element.id) { index, scene in
                        VStack(alignment: .leading, spacing: 12) {
                            HStack(alignment: .firstTextBaseline, spacing: 10) {
                                Text("SCENE \(index + 1)")
                                    .font(.system(size: 10, weight: .bold))
                                    .foregroundStyle(Theme.typeText)
                                    .padding(.horizontal, 7)
                                    .padding(.vertical, 3)
                                    .background(Theme.typeText.opacity(0.12), in: Capsule())
                                Text(scene.title).font(.system(size: 17, weight: .semibold))
                            }
                            Text(scene.summary)
                                .font(.callout)
                                .foregroundStyle(.secondary)
                                .frame(maxWidth: 760, alignment: .leading)
                            LazyVGrid(columns: [GridItem(.adaptive(minimum: 230, maximum: 360), spacing: 16, alignment: .top)], spacing: 16) {
                                ForEach(project.shots(inScene: scene.id)) { shot in
                                    ShotCard(shot: shot, selected: selectedShot == shot.id)
                                        .onTapGesture { selectedShot = shot.id }
                                }
                            }
                        }
                    }
                }
                .padding(24)
            }
            .background(DotGrid())
            .inspector(isPresented: Binding(get: { selectedShot != nil }, set: { if !$0 { selectedShot = nil } })) {
                if let id = selectedShot, let shot = project.shots.first(where: { $0.id == id }) {
                    ShotInspector(shot: shot, project: project)
                        .id(shot.id)
                        .background(Theme.panel)
                        .inspectorColumnWidth(min: 340, ideal: 400, max: 560)
                }
            }
        }
    }

    /// Outline scenes, or one catch-all scene if the outline is missing.
    private var scenes: [SceneOutline] {
        if let scenes = project.outline?.scenes, !scenes.isEmpty { return scenes }
        let ids = project.shots.map(\.sceneId).reduce(into: [String]()) { if !$0.contains($1) { $0.append($1) } }
        return ids.map { SceneOutline(id: $0, title: $0, summary: "", locationId: "", characterIds: []) }
    }
}

struct ShotCard: View {
    @Environment(AppModel.self) private var model
    var shot: Shot
    var selected: Bool
    @SwiftUI.State private var hovering = false

    var body: some View {
        NodePanel(title: shot.id, symbol: "rectangle.on.rectangle", type: shot.video == nil ? .image : .video,
                  highlighted: hovering, selected: selected) {
            HStack(spacing: 5) {
                if shot.video != nil {
                    Image(systemName: "play.fill").font(.system(size: 9)).foregroundStyle(Theme.typeVideo)
                }
                Text(shot.framing.title)
                    .font(.system(size: 10.5, weight: .medium))
                    .foregroundStyle(.secondary)
            }
        } content: {
            VStack(alignment: .leading, spacing: 8) {
                AspectImage(url: shot.image.flatMap { model.fileURL($0) }, ratio: 16 / 10, cornerRadius: 0)
                VStack(alignment: .leading, spacing: 6) {
                    Text(shot.action)
                        .font(.system(size: 12))
                        .lineLimit(3)
                    if let line = shot.dialogue.first {
                        Text("“\(line.text)”")
                            .font(.system(size: 11))
                            .italic()
                            .foregroundStyle(Theme.typeText)
                            .lineLimit(2)
                    } else if !shot.narration.isEmpty {
                        Text(shot.narration)
                            .font(.system(size: 11))
                            .foregroundStyle(.secondary)
                            .lineLimit(2)
                    }
                }
                .padding(.horizontal, 10)
                .padding(.bottom, 10)
            }
        }
        .contentShape(Rectangle())
        .onHover { hovering = $0 }
        .animation(.easeOut(duration: 0.12), value: hovering)
    }
}

struct ShotInspector: View {
    @Environment(AppModel.self) private var model
    var shot: Shot
    var project: Project
    @SwiftUI.State private var action = ""
    @SwiftUI.State private var framing: Framing = .medium
    @SwiftUI.State private var narration = ""
    @SwiftUI.State private var dialogue: [DialogueLine] = []
    @SwiftUI.State private var player: AVPlayer?

    private var busy: Bool { model.isBusy(project.id) }
    private var changed: Bool {
        action != shot.action || framing != shot.framing || narration != shot.narration || dialogue != shot.dialogue
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                preview

                HStack {
                    Text("Shot \(shot.id)").font(.headline)
                    Spacer()
                    Text("Take \(shot.seedOffset + 1)").font(.caption).foregroundStyle(.secondary)
                }

                Picker("Framing", selection: $framing) {
                    ForEach(Framing.allCases) { Text($0.title).tag($0) }
                }
                .pickerStyle(.segmented)
                .labelsHidden()

                field("What the camera sees") {
                    TextEditor(text: $action)
                        .font(.callout)
                        .scrollContentBackground(.hidden)
                        .padding(6)
                        .frame(height: 120)
                        .background(Theme.surface, in: RoundedRectangle(cornerRadius: 8))
                }

                field("Narration") {
                    TextField("Caption or voice-over", text: $narration, axis: .vertical)
                        .textFieldStyle(.roundedBorder)
                }

                if !dialogue.isEmpty {
                    field("Dialogue") {
                        ForEach(dialogue.indices, id: \.self) { index in
                            VStack(alignment: .leading, spacing: 3) {
                                Text(speakerName(dialogue[index].speaker))
                                    .font(.caption.weight(.bold))
                                    .foregroundStyle(Theme.accent)
                                TextField("Line", text: $dialogue[index].text, axis: .vertical)
                                    .textFieldStyle(.roundedBorder)
                            }
                        }
                    }
                }

                Divider()

                VStack(spacing: 8) {
                    Button {
                        Task {
                            guard await save() else { return }
                            model.run(.images, StepRequest(only: [shot.id]))
                        }
                    } label: {
                        Label(changed ? "Save & Redraw" : "Redraw", systemImage: "paintbrush.pointed")
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.borderedProminent)

                    HStack {
                        Button {
                            Task {
                                guard await save() else { return }
                                model.run(.images, StepRequest(only: [shot.id], reroll: true))
                            }
                        } label: {
                            Label("New Take", systemImage: "dice").frame(maxWidth: .infinity)
                        }
                        Button {
                            Task {
                                guard await save() else { return }
                                model.run(.video, StepRequest(only: [shot.id], reroll: shot.video != nil))
                            }
                        } label: {
                            Label(shot.video == nil ? "Animate" : "New Clip", systemImage: "film").frame(maxWidth: .infinity)
                        }
                        .disabled(shot.image == nil)
                    }

                    if changed {
                        Button("Save Text Only") { Task { await save() } }
                            .buttonStyle(.link)
                    }
                    Text("A redraw takes about 20 seconds. Animating takes several minutes per clip on this Mac.")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .multilineTextAlignment(.center)
                }
                .controlSize(.large)
                .disabled(busy)
            }
            .padding(16)
        }
        .onAppear(perform: load)
        .onChange(of: shot) { _, _ in load() }
        .onChange(of: model.mediaVersion) { _, _ in loadPlayer() }
        .onDisappear { player?.pause() }
    }

    @ViewBuilder
    private var preview: some View {
        if let player {
            VideoPlayer(player: player)
                .aspectRatio(16 / 9, contentMode: .fit)
                .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
        } else {
            AspectImage(url: shot.image.flatMap { model.fileURL($0) }, ratio: 16 / 10)
        }
    }

    private func field<Content: View>(_ title: String, @ViewBuilder content: () -> Content) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(title).font(.caption.weight(.semibold)).foregroundStyle(.secondary)
            content()
        }
    }

    private func speakerName(_ id: String) -> String {
        project.bible?.character(id)?.name ?? "Narrator"
    }

    private func load() {
        action = shot.action
        framing = shot.framing
        narration = shot.narration
        dialogue = shot.dialogue
        loadPlayer()
    }

    private func loadPlayer() {
        player?.pause()
        if let video = shot.video, let url = model.fileURL(video) {
            let player = AVPlayer(url: url)
            player.actionAtItemEnd = .none
            self.player = player
        } else {
            player = nil
        }
    }

    /// Saves pending edits; true if there was nothing to save or it worked.
    @discardableResult
    private func save() async -> Bool {
        guard changed else { return true }
        return await model.updateShot(
            shot.id,
            ShotPatch(action: action, framing: framing, narration: narration, dialogue: dialogue)
        )
    }
}

// MARK: Export

@MainActor
@Observable
final class PlayerHolder {
    var player: AVPlayer?
}

struct ExportTab: View {
    @Environment(AppModel.self) private var model
    var project: Project
    // A reference holder: loadPlayer() changes the holder, never the view, which
    // the macOS 27 SDK compiler refuses here as "self is immutable".
    @SwiftUI.State private var animatic = PlayerHolder()

    private var exports: Exports? { model.exports }
    private var busy: Bool { model.isBusy(project.id) }
    private var ready: Bool { project.shots.contains { $0.image != nil } && project.shots.allSatisfy { $0.image != nil } }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                SectionTitle(
                    title: "Export",
                    subtitle: ready ? "Build any format from the same panels." : "Draw every panel first; exports use them all."
                )

                ExportCard(
                    title: "Comic", symbol: "book.pages",
                    detail: "Laid-out pages with captions and speech bubbles, as a PDF.",
                    available: exports?.comic.pdf != nil,
                    disabled: busy || !ready,
                    build: { model.run(.comic) },
                    open: { model.open(exports?.comic.pdf) },
                    reveal: { model.reveal(exports?.comic.pdf) }
                ) {
                    if let pages = exports?.comic.pages, !pages.isEmpty {
                        ScrollView(.horizontal) {
                            HStack(spacing: 12) {
                                ForEach(pages, id: \.self) { page in
                                    AspectImage(url: model.fileURL(page), ratio: 2 / 3, cornerRadius: 6)
                                        .frame(height: 230)
                                        .onTapGesture { model.open(page) }
                                }
                            }
                        }
                    }
                }

                ExportCard(
                    title: "Visual Novel", symbol: "text.bubble",
                    detail: "A click-through player that opens in your browser, plus a Ren'Py project.",
                    available: exports?.vn.html != nil,
                    disabled: busy || !ready,
                    build: { model.run(.vn) },
                    open: { model.open(exports?.vn.html) },
                    reveal: { model.reveal(exports?.vn.renpy) }
                ) {
                    EmptyView()
                }

                ExportCard(
                    title: "Animatic", symbol: "film",
                    detail: "Voiced film with subtitles. Shots with clips play them; the rest pan across the panel.",
                    available: exports?.animatic.mp4 != nil,
                    disabled: busy || !ready,
                    build: { model.run(.animatic) },
                    open: { model.open(exports?.animatic.mp4) },
                    reveal: { model.reveal(exports?.animatic.mp4) }
                ) {
                    if let player = animatic.player {
                        VideoPlayer(player: player)
                            .aspectRatio(16 / 9, contentMode: .fit)
                            .frame(maxWidth: 720)
                            .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
                    }
                }
            }
            .padding(24)
            .frame(maxWidth: 1000, alignment: .leading)
            .frame(maxWidth: .infinity)
        }
        .background(DotGrid())
        .onAppear(perform: loadPlayer)
        .onChange(of: model.mediaVersion) { _, _ in loadPlayer() }
        .onChange(of: exports?.animatic.mp4) { _, _ in loadPlayer() }
        .onDisappear { animatic.player?.pause() }
    }

    private func loadPlayer() {
        animatic.player?.pause()
        if let path = exports?.animatic.mp4, let url = model.fileURL(path) {
            animatic.player = AVPlayer(url: url)
        } else {
            animatic.player = nil
        }
    }
}

struct ExportCard<Preview: View>: View {
    var title: String
    var symbol: String
    var detail: String
    var available: Bool
    var disabled: Bool
    var build: () -> Void
    var open: () -> Void
    var reveal: () -> Void
    @ViewBuilder var preview: () -> Preview

    var body: some View {
        NodePanel(title: title, symbol: symbol, type: .file) {
            if available {
                Badge(text: "Ready", symbol: "checkmark", tint: Theme.typeFile)
            }
        } content: {
            VStack(alignment: .leading, spacing: 14) {
                HStack(spacing: 10) {
                    Text(detail).font(.callout).foregroundStyle(.secondary)
                    Spacer()
                    if available {
                        Button("Show in Finder", action: reveal)
                        Button("Open", action: open)
                    }
                    Button(available ? "Rebuild" : "Build", action: build)
                        .buttonStyle(.borderedProminent)
                        .disabled(disabled)
                }
                preview()
            }
            .padding(14)
        }
    }
}
#endif
