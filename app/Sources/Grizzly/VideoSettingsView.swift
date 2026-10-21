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
                    defaultable("Clip length", value: $video.clipSeconds, fallback: 1.7) { seconds in
                        HStack {
                            Slider(value: seconds, in: 0.7...5, step: 0.1)
                            Text("\(seconds.wrappedValue, specifier: "%.1f")s · \(VideoSettings.frames(forSeconds: seconds.wrappedValue)) frames")
                                .monospacedDigit()
                                .foregroundStyle(.secondary)
                                .frame(width: 130, alignment: .trailing)
                        }
                    }
                    defaultable("Steps", value: $video.steps, fallback: 30) { steps in
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

    /// A setting that is either the model's default (nil) or a chosen value.
    @ViewBuilder
    private func defaultable<Value: Sendable, Content: View>(
        _ title: String, value: Binding<Value?>, fallback: Value,
        @ViewBuilder content: (Binding<Value>) -> Content
    ) -> some View {
        Toggle(title, isOn: Binding(
            get: { value.wrappedValue != nil },
            set: { value.wrappedValue = $0 ? fallback : nil }
        ))
        if value.wrappedValue != nil {
            content(Binding(get: { value.wrappedValue ?? fallback }, set: { value.wrappedValue = $0 }))
        }
    }
}
#endif
