#if os(macOS)
import AppKit
import GrizzlyCore
import SwiftUI

struct WelcomeView: View {
    @Environment(AppModel.self) private var model

    var body: some View {
        VStack(spacing: 28) {
            VStack(spacing: 10) {
                Image(systemName: "pawprint.fill")
                    .font(.system(size: 54))
                    .foregroundStyle(Theme.accent)
                Text("Grizzly")
                    .font(.system(size: 44, weight: .bold, design: .serif))
                Text("Write, cast and illustrate stories on this Mac.")
                    .font(.title3)
                    .foregroundStyle(.secondary)
            }
            HStack(spacing: 16) {
                step("1", "Pitch an idea", "A premise is enough. The writer builds the cast, the world and a storyboard.")
                step("2", "Shape it", "Edit any character or panel, redraw it, or ask for a new take.")
                step("3", "Export", "A comic, a visual novel or a voiced animatic with animated clips.")
            }
            .frame(maxWidth: 820)
            Button {
                model.showNewStory = true
            } label: {
                Label("New Story", systemImage: "plus")
                    .padding(.horizontal, 12)
            }
            .buttonStyle(.borderedProminent)
            .controlSize(.extraLarge)
            Text("Everything runs offline: no accounts, no uploads.")
                .font(.caption)
                .foregroundStyle(.tertiary)
        }
        .padding(40)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private func step(_ number: String, _ title: String, _ detail: String) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(number)
                .font(.headline.monospacedDigit())
                .frame(width: 28, height: 28)
                .background(Theme.accent.opacity(0.2), in: Circle())
                .foregroundStyle(Theme.accent)
            Text(title).font(.headline)
            Text(detail).font(.callout).foregroundStyle(.secondary)
            Spacer(minLength: 0)
        }
        .padding(16)
        .frame(maxWidth: .infinity, minHeight: 150, alignment: .topLeading)
        .card()
    }
}

struct EngineStartingView: View {
    @Environment(AppModel.self) private var model

    var body: some View {
        VStack(spacing: 18) {
            ProgressView().controlSize(.large)
            Text("Starting the Grizzly engine…").font(.title2.weight(.semibold))
            Text("Loading Python and the model registry. Models themselves load when a step needs them.")
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
            if !model.engineLog.isEmpty {
                EngineLogView().frame(maxWidth: 720, maxHeight: 200)
            }
        }
        .padding(40)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

struct EngineFailedView: View {
    @Environment(AppModel.self) private var model
    var message: String

    var body: some View {
        VStack(spacing: 18) {
            Image(systemName: "bolt.horizontal.circle")
                .font(.system(size: 48))
                .foregroundStyle(.orange)
            Text("The engine isn't running").font(.title2.weight(.semibold))
            Text(message)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
                .textSelection(.enabled)
                .frame(maxWidth: 560)
            Text("Engine folder: \(model.engineDirectory)")
                .font(.callout.monospaced())
                .foregroundStyle(.secondary)
            HStack {
                Button("Choose Grizzly Folder…") { chooseEngineFolder(model) }
                Button("Try Again") { Task { await model.restartEngine() } }
                    .buttonStyle(.borderedProminent)
            }
            if !model.engineLog.isEmpty {
                DisclosureGroup("Engine log") {
                    EngineLogView().frame(height: 220)
                }
                .frame(maxWidth: 720)
            }
        }
        .padding(40)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

struct EngineLogView: View {
    @Environment(AppModel.self) private var model

    var body: some View {
        ScrollViewReader { proxy in
            ScrollView {
                Text(model.engineLog.suffix(200).joined(separator: "\n"))
                    .font(.caption.monospaced())
                    .foregroundStyle(.secondary)
                    .textSelection(.enabled)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(10)
                Color.clear.frame(height: 1).id("end")
            }
            .onChange(of: model.engineLog.count) { _, _ in
                proxy.scrollTo("end", anchor: .bottom)
            }
        }
        .card()
    }
}

@MainActor
func chooseEngineFolder(_ model: AppModel) {
    let panel = NSOpenPanel()
    panel.canChooseDirectories = true
    panel.canChooseFiles = false
    panel.allowsMultipleSelection = false
    panel.prompt = "Use Folder"
    panel.message = "Choose your Grizzly checkout (the folder with pyproject.toml and .venv)."
    if panel.runModal() == .OK, let url = panel.url {
        model.engineDirectory = url.path
        Task { await model.restartEngine() }
    }
}

struct SettingsView: View {
    @Environment(AppModel.self) private var model

    var body: some View {
        @Bindable var model = model
        Form {
            Section("Engine") {
                LabeledContent("Grizzly folder") {
                    HStack {
                        Text(model.engineDirectory)
                            .lineLimit(1)
                            .truncationMode(.middle)
                        Button("Choose…") { chooseEngineFolder(model) }
                    }
                }
                Picker("Hardware profile", selection: $model.profile) {
                    ForEach(AppModel.profiles, id: \.self) { Text($0).tag($0) }
                }
                TextField("Port", value: $model.port, format: .number.grouping(.never))
                Button("Restart Engine") { Task { await model.restartEngine() } }
            }
            Section("Models") {
                EngineInfoView()
            }
        }
        .formStyle(.grouped)
        .frame(width: 540)
        .padding(.vertical, 8)
    }
}

// MARK: New story

struct NewStorySheet: View {
    @Environment(AppModel.self) private var model
    @Environment(\.dismiss) private var dismiss
    @State private var title = ""
    @State private var premise = ""
    @State private var format: StoryFormat = .comic
    @State private var scenes = 4
    @State private var shots = 4
    @State private var creating = false

    private var canCreate: Bool {
        !creating && !title.trimmingCharacters(in: .whitespaces).isEmpty
            && premise.trimmingCharacters(in: .whitespacesAndNewlines).count >= 10
    }

    /// From the 24GB M5 Pro run: ~1 min writing, ~35 s per portrait, ~19 s per panel.
    private var minutes: Int {
        max(1, Int(((60 + 3 * 35 + Double(scenes * shots) * 19) / 60).rounded()))
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 20) {
            VStack(alignment: .leading, spacing: 4) {
                Text("New Story").font(Theme.titleFont)
                Text("Describe an idea. Grizzly writes it, casts it and draws it, all on this Mac.")
                    .foregroundStyle(.secondary)
            }

            TextField("Title", text: $title)
                .textFieldStyle(.plain)
                .font(.title2.weight(.semibold))
                .padding(10)
                .card()

            VStack(alignment: .leading, spacing: 6) {
                Text("Premise").font(.headline)
                ZStack(alignment: .topLeading) {
                    TextEditor(text: $premise)
                        .font(.body)
                        .scrollContentBackground(.hidden)
                        .padding(8)
                    if premise.isEmpty {
                        Text("In a city of brass towers and airships, a retired safecracker and her teenage son must steal back…")
                            .foregroundStyle(.tertiary)
                            .padding(.horizontal, 13)
                            .padding(.vertical, 16)
                            .allowsHitTesting(false)
                    }
                }
                .frame(minHeight: 130)
                .card()
            }

            VStack(alignment: .leading, spacing: 8) {
                Text("Format").font(.headline)
                HStack(spacing: 12) {
                    ForEach(StoryFormat.allCases) { option in
                        FormatCard(format: option, selected: option == format) { format = option }
                    }
                }
            }

            HStack(spacing: 24) {
                Stepper("Scenes: \(scenes)", value: $scenes, in: 1...8)
                Stepper("Panels per scene: \(shots)", value: $shots, in: 2...6)
                Spacer()
                Text("\(scenes * shots) panels · about \(minutes) min")
                    .foregroundStyle(.secondary)
                    .monospacedDigit()
            }

            HStack {
                Spacer()
                Button("Cancel") { dismiss() }
                    .keyboardShortcut(.cancelAction)
                Button {
                    creating = true
                    Task {
                        await model.createStory(
                            title: title.trimmingCharacters(in: .whitespaces),
                            premise: premise.trimmingCharacters(in: .whitespacesAndNewlines),
                            format: format, scenes: scenes, shots: shots
                        )
                        dismiss()
                    }
                } label: {
                    if creating {
                        ProgressView().controlSize(.small)
                    } else {
                        Label("Write & Illustrate", systemImage: "sparkles")
                    }
                }
                .buttonStyle(.borderedProminent)
                .keyboardShortcut(.defaultAction)
                .disabled(!canCreate)
            }
        }
        .padding(28)
        .frame(width: 680)
    }
}

struct FormatCard: View {
    var format: StoryFormat
    var selected: Bool
    var action: () -> Void
    @State private var hovering = false

    var body: some View {
        Button(action: action) {
            VStack(spacing: 8) {
                Image(systemName: format.symbol)
                    .font(.system(size: 26))
                    .foregroundStyle(selected ? Theme.accent : .secondary)
                Text(format.title).font(.headline)
                Text(format.blurb)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
                    .fixedSize(horizontal: false, vertical: true)
            }
            .frame(maxWidth: .infinity, minHeight: 120)
            .padding(14)
            .card(highlighted: hovering, selected: selected)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .onHover { hovering = $0 }
    }
}
#endif
