#if os(macOS)
import AppKit
import GrizzlyCore
import SwiftUI

final class AppDelegate: NSObject, NSApplicationDelegate {
    weak var model: AppModel?

    func applicationDidFinishLaunching(_ notification: Notification) {
        // Needed when launched with `swift run` rather than as a bundled .app.
        NSApp.setActivationPolicy(.regular)
        NSApp.activate(ignoringOtherApps: true)
    }

    func applicationWillTerminate(_ notification: Notification) {
        // The engine holds gigabytes of model weights; never leave it behind.
        model?.stopEngine()
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }
}

@main
struct GrizzlyApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) private var delegate
    @State private var model = AppModel()

    var body: some Scene {
        WindowGroup("Grizzly") {
            ContentView()
                .environment(model)
                .frame(minWidth: 1080, minHeight: 680)
                .preferredColorScheme(.dark)
                .tint(Theme.accent)
                .task {
                    delegate.model = model
                    await model.startEngine()
                }
        }
        .windowToolbarStyle(.unified)
        .commands {
            CommandGroup(replacing: .newItem) {
                Button("New Story…") { model.showNewStory = true }
                    .keyboardShortcut("n")
                    .disabled(model.engineState != .running)
            }
        }

        Settings {
            SettingsView()
                .environment(model)
                .preferredColorScheme(.dark)
        }
    }
}
#else
@main
enum GrizzlyStub {
    static func main() {
        print("Grizzly.app runs on macOS. GrizzlyCore builds and tests on any platform.")
    }
}
#endif
