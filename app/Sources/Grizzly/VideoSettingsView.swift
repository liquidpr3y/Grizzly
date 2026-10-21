#if os(macOS)
import GrizzlyCore
import SwiftUI

/// Project-wide video options: how clips are generated and how the animatic is cut.
struct VideoSettingsSheet: View {
    @Environment(AppModel.self) private var model
    @Environment(\.dismiss) private var dismiss
    var project: Project
    @State private var video = VideoSettings()
    @State private var animatic = AnimaticSettings()

    private var busy: Bool { model.isBusy(project.id) }
    private var changed: Bool { video != project.video || animatic != project.animatic }

    var body: some View {
        VStack(spacing: 0) {
            Form {
                Section {
                    Picker("Aspect ratio", selection: $video.aspect) {
                        ForEach(VideoAspect.allCases) { Text($0.title).tag($0) }
                    }
                    Picker("Quality", selection: $video.quality) {
                        Text("Model default").tag(VideoQuality?.none)
                        ForEach(VideoQuality.allCases) { Text($0.title).tag(VideoQuality?.some($0)) }
                    }
                    Picker("Camera move", selection: $video.camera) {
                        ForEach(CameraMove.allCases) { Text($0.title).tag($0) }
                    }
                    DefaultableSetting(title: "Set clip length", value: $video.clipSeconds, fallback: 1.7) { seconds in
                        ClipLengthSlider(seconds: seconds)
                    }
                    DefaultableSetting(title: "Set steps", value: $video.steps, fallback: 30) { steps in
                        Stepper("\(steps.wrappedValue) steps", value: steps, in: 4...60, step: 2)
                    }
                } header: {
                    Text("Clips")
                } footer: {
                    Text("Longer clips, more steps and higher quality all take longer and use more memory. Changing the aspect ratio also reshapes panels drawn after the change.")
                        .foregroundStyle(.secondary)
                }

                Section("Animatic") {
                    Picker("Frame rate", selection: $animatic.fps) {
                        ForEach([24, 25, 30, 60], id: \.self) { Text("\($0) fps").tag($0) }
                    }
                }
            }
            .formStyle(.grouped)

            Divider()
            HStack {
                Button("Reset to Defaults") {
                    video = VideoSettings()
                    animatic = AnimaticSettings()
                }
                Spacer()
                Button("Cancel", role: .cancel) { dismiss() }
                    .keyboardShortcut(.cancelAction)
                Button("Save") {
                    Task {
                        if await model.updateSettings(SettingsPatch(video: video, animatic: animatic)) { dismiss() }
                    }
                }
                .keyboardShortcut(.defaultAction)
                .buttonStyle(.borderedProminent)
                .disabled(!changed || busy)
            }
            .padding(16)
        }
        .frame(width: 520)
        .onAppear {
            video = project.video
            animatic = project.animatic
        }
    }
}

/// A setting that is either inherited (nil) or a chosen value.
struct DefaultableSetting<Value: Sendable, Content: View>: View {
    var title: String
    @Binding var value: Value?
    var fallback: Value
    @ViewBuilder var content: (Binding<Value>) -> Content

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Toggle(title, isOn: Binding(
                get: { value != nil },
                set: { value = $0 ? (value ?? fallback) : nil }
            ))
            if value != nil {
                content(Binding(get: { value ?? fallback }, set: { value = $0 }))
            }
        }
    }
}

struct ClipLengthSlider: View {
    @Binding var seconds: Double

    var body: some View {
        HStack {
            Slider(value: $seconds, in: 0.7...5, step: 0.1)
            Text("\(seconds, specifier: "%.1f")s · \(VideoSettings.frames(forSeconds: seconds)) frames")
                .monospacedDigit()
                .foregroundStyle(.secondary)
                .frame(width: 130, alignment: .trailing)
        }
    }
}
#endif
