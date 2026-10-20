#if os(macOS)
import GrizzlyCore
import SwiftUI

enum ProjectTab: String, CaseIterable, Identifiable {
    case story = "Story"
    case cast = "Cast"
    case storyboard = "Storyboard"
    case export = "Export"

    var id: String { rawValue }
}

struct ProjectView: View {
    @Environment(AppModel.self) private var model
    var envelope: ProjectEnvelope
    @State private var tab: ProjectTab = .storyboard

    private var project: Project { envelope.project }
    private var busy: Bool { model.isBusy(project.id) }

    var body: some View {
        VStack(spacing: 0) {
            header
                .padding(.horizontal, 24)
                .padding(.top, 16)
                .padding(.bottom, 12)
            PipelineBar(status: envelope.status, exports: model.exports, job: model.job(for: project.id))
                .padding(.horizontal, 24)
                .padding(.bottom, 14)
            Divider()
            Group {
                switch tab {
                case .story: StoryTab(project: project)
                case .cast: CastTab(project: project)
                case .storyboard: StoryboardTab(project: project)
                case .export: ExportTab(project: project)
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
        .navigationTitle(project.title)
        .toolbar {
            ToolbarItem(placement: .principal) {
                Picker("View", selection: $tab) {
                    ForEach(ProjectTab.allCases) { Text($0.rawValue).tag($0) }
                }
                .pickerStyle(.segmented)
                .frame(width: 380)
            }
            ToolbarItem(placement: .primaryAction) {
                Button {
                    model.run(.all, StepRequest())
                } label: {
                    Label(primaryTitle, systemImage: "sparkles")
                }
                .buttonStyle(.borderedProminent)
                .disabled(busy)
                .help("Write and illustrate whatever is missing, then build the \(project.format.title.lowercased()) export")
            }
        }
        .onAppear {
            if !envelope.status.shots { tab = .story }
        }
    }

    private var primaryTitle: String {
        if !envelope.status.bible { return "Write Story" }
        if !envelope.status.images { return "Continue" }
        return "Rebuild Export"
    }

    private var header: some View {
        HStack(alignment: .top, spacing: 16) {
            VStack(alignment: .leading, spacing: 6) {
                Text(project.bible?.title ?? project.title)
                    .font(Theme.titleFont)
                    .lineLimit(1)
                Text(project.bible?.logline ?? project.premise)
                    .foregroundStyle(.secondary)
                    .lineLimit(2)
            }
            Spacer()
            Badge(text: project.format.title, symbol: project.format.symbol, tint: Theme.accent)
                .font(.callout)
        }
    }
}

// MARK: Pipeline progress

struct PipelineBar: View {
    var status: ProjectStatus
    var exports: Exports?
    var job: Job?

    private struct Stage {
        var title: String
        var symbol: String
        var done: Bool
    }

    private var stages: [Stage] {
        let exported = exports.map { $0.comic.pdf != nil || $0.vn.html != nil || $0.animatic.mp4 != nil } ?? false
        return [
            Stage(title: "Story", symbol: "text.book.closed", done: status.bible && status.outline && status.shots),
            Stage(title: "Cast", symbol: "person.2", done: status.portraits),
            Stage(title: "Panels", symbol: "photo.on.rectangle.angled", done: status.images),
            Stage(title: "Export", symbol: "square.and.arrow.up", done: exported),
        ]
    }

    private var activeIndex: Int? {
        guard let job, !job.state.isFinished else { return nil }
        return job.stageIndex
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 0) {
                ForEach(Array(stages.enumerated()), id: \.offset) { index, stage in
                    stageView(stage, active: index == activeIndex)
                    if index < stages.count - 1 {
                        Capsule()
                            .fill(stage.done ? Theme.accent.opacity(0.7) : Theme.stroke)
                            .frame(height: 2)
                            .padding(.horizontal, 8)
                    }
                }
            }
            if let job, !job.state.isFinished {
                HStack(spacing: 12) {
                    if let fraction = job.fraction {
                        ProgressView(value: Double(fraction.done - 1), total: Double(fraction.total))
                            .frame(width: 240)
                        Text("\(AppModel.title(of: job.stage ?? job.step)) · \(fraction.done) of \(fraction.total) · \(job.progressLabel)")
                    } else {
                        ProgressView().controlSize(.small)
                        Text(job.state == .queued ? "Queued…" : "\(AppModel.title(of: job.stage ?? job.step))…")
                    }
                }
                .font(.callout)
                .foregroundStyle(.secondary)
                .transition(.opacity)
            }
        }
        .animation(.easeOut(duration: 0.2), value: job?.progress)
    }

    private func stageView(_ stage: Stage, active: Bool) -> some View {
        HStack(spacing: 8) {
            ZStack {
                Circle()
                    .fill(stage.done ? Theme.accent : (active ? Theme.accent.opacity(0.25) : Theme.surface))
                    .frame(width: 28, height: 28)
                if active {
                    ProgressView().controlSize(.small)
                } else {
                    Image(systemName: stage.done ? "checkmark" : stage.symbol)
                        .font(.caption.weight(.bold))
                        .foregroundStyle(stage.done ? .black : .secondary)
                }
            }
            Text(stage.title)
                .font(.callout.weight(active ? .semibold : .regular))
                .foregroundStyle(stage.done || active ? .primary : .secondary)
        }
        .fixedSize()
    }
}

// MARK: Story

struct StoryTab: View {
    @Environment(AppModel.self) private var model
    var project: Project
    @State private var artStyle = ""

    var body: some View {
        if let bible = project.bible {
            ScrollView {
                VStack(alignment: .leading, spacing: 24) {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Premise").font(.caption.weight(.semibold)).foregroundStyle(.secondary)
                        Text(project.premise).font(.title3)
                        HStack(spacing: 8) {
                            if !bible.genre.isEmpty { Badge(text: bible.genre, symbol: "theatermasks") }
                            if !bible.tone.isEmpty { Badge(text: bible.tone, symbol: "cloud.sun") }
                        }
                    }

                    VStack(alignment: .leading, spacing: 8) {
                        SectionTitle(title: "Art direction", subtitle: "Added to every image. Describe technique and palette, not characters.")
                        TextEditor(text: $artStyle)
                            .font(.body)
                            .scrollContentBackground(.hidden)
                            .padding(8)
                            .frame(height: 70)
                            .card()
                        HStack {
                            Spacer()
                            Button("Save Art Direction") {
                                Task { await model.updateBible(BiblePatch(artStyle: artStyle)) }
                            }
                            .disabled(artStyle == bible.artStyle || model.isBusy(project.id))
                        }
                    }

                    SectionTitle(title: "Outline", subtitle: "\(project.outline?.scenes.count ?? 0) scenes · \(project.shots.count) panels")
                    ForEach(Array((project.outline?.scenes ?? []).enumerated()), id: \.element.id) { index, scene in
                        SceneCard(number: index + 1, scene: scene, bible: bible, panels: project.shots(inScene: scene.id).count)
                    }
                }
                .padding(24)
                .frame(maxWidth: 920, alignment: .leading)
                .frame(maxWidth: .infinity)
            }
            .onAppear { artStyle = bible.artStyle }
        } else {
            ContentUnavailableView {
                Label("Not written yet", systemImage: "text.book.closed")
            } description: {
                Text(project.premise)
            } actions: {
                Button("Write Story") { model.run(.all, StepRequest()) }
                    .buttonStyle(.borderedProminent)
                    .disabled(model.isBusy(project.id))
            }
        }
    }
}

struct SceneCard: View {
    var number: Int
    var scene: SceneOutline
    var bible: StoryBible
    var panels: Int

    var body: some View {
        HStack(alignment: .top, spacing: 14) {
            Text("\(number)")
                .font(.title3.weight(.bold).monospacedDigit())
                .foregroundStyle(Theme.accent)
                .frame(width: 28)
            VStack(alignment: .leading, spacing: 6) {
                Text(scene.title).font(.headline)
                Text(scene.summary).foregroundStyle(.secondary)
                HStack(spacing: 6) {
                    if let location = bible.location(scene.locationId) {
                        Badge(text: location.name, symbol: "mappin.and.ellipse")
                    }
                    ForEach(scene.characterIds, id: \.self) { id in
                        if let character = bible.character(id) {
                            Badge(text: character.name, symbol: "person.fill")
                        }
                    }
                    Spacer()
                    Text("\(panels) panels").font(.caption).foregroundStyle(.tertiary)
                }
            }
        }
        .padding(14)
        .card()
    }
}

// MARK: Cast

struct CastTab: View {
    var project: Project

    var body: some View {
        if let bible = project.bible {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    SectionTitle(
                        title: "Cast",
                        subtitle: "Every panel copies these portraits. Get them right before drawing panels."
                    )
                    LazyVGrid(columns: [GridItem(.adaptive(minimum: 250, maximum: 340), spacing: 20, alignment: .top)], spacing: 20) {
                        ForEach(bible.characters) { character in
                            CharacterCard(character: character, projectID: project.id)
                        }
                    }
                }
                .padding(24)
            }
        } else {
            ContentUnavailableView("No cast yet", systemImage: "person.2", description: Text("Write the story first."))
        }
    }
}

struct CharacterCard: View {
    @Environment(AppModel.self) private var model
    var character: StoryCharacter
    var projectID: String
    @State private var appearance = ""
    @State private var voice = ""

    private var busy: Bool { model.isBusy(projectID) }
    private var changed: Bool { appearance != character.appearance || voice != character.voice }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            AspectImage(url: character.portrait.flatMap { model.fileURL($0) }, ratio: 896 / 1152)
            VStack(alignment: .leading, spacing: 2) {
                Text(character.name).font(.title3.weight(.bold))
                Text(character.role.capitalized).font(.caption.weight(.semibold)).foregroundStyle(Theme.accent)
            }
            if !character.personality.isEmpty {
                Text(character.personality).font(.callout).foregroundStyle(.secondary)
            }
            VStack(alignment: .leading, spacing: 4) {
                Text("Appearance").font(.caption.weight(.semibold)).foregroundStyle(.secondary)
                TextEditor(text: $appearance)
                    .font(.callout)
                    .scrollContentBackground(.hidden)
                    .padding(6)
                    .frame(height: 96)
                    .background(Theme.surface, in: RoundedRectangle(cornerRadius: 8))
            }
            TextField("Voice (macOS voice name, e.g. Daniel)", text: $voice)
                .textFieldStyle(.roundedBorder)
            HStack {
                Button("Save") { Task { await save() } }
                    .disabled(!changed)
                Spacer()
                Button {
                    Task {
                        if changed { guard await save() else { return } }
                        model.run(.portraits, StepRequest(only: [character.id], reroll: true))
                    }
                } label: {
                    Label("New Portrait", systemImage: "arrow.triangle.2.circlepath")
                }
            }
            .disabled(busy)
        }
        .padding(14)
        .card()
        .onAppear(perform: load)
        .onChange(of: character) { _, _ in load() }
    }

    private func load() {
        appearance = character.appearance
        voice = character.voice
    }

    @discardableResult
    private func save() async -> Bool {
        await model.updateCharacter(character.id, CharacterPatch(appearance: appearance, voice: voice))
    }
}
#endif
