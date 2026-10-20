#if os(macOS)
import GrizzlyCore
import SwiftUI

struct ContentView: View {
    @Environment(AppModel.self) private var model

    var body: some View {
        @Bindable var model = model
        NavigationSplitView {
            LibrarySidebar()
                .navigationSplitViewColumnWidth(min: 250, ideal: 290, max: 380)
        } detail: {
            detail
        }
        .sheet(isPresented: $model.showNewStory) {
            NewStorySheet()
        }
        .alert(
            "Something went wrong",
            isPresented: Binding(get: { model.alert != nil }, set: { if !$0 { model.alert = nil } })
        ) {
            Button("OK", role: .cancel) {}
        } message: {
            Text(model.alert ?? "")
        }
    }

    @ViewBuilder
    private var detail: some View {
        switch model.engineState {
        case .running:
            if let envelope = model.current {
                ProjectView(envelope: envelope)
                    .id(envelope.project.id)
            } else if model.selection != nil {
                ProgressView()
            } else {
                WelcomeView()
            }
        case .stopped, .starting:
            EngineStartingView()
        case let .failed(message):
            EngineFailedView(message: message)
        }
    }
}

// MARK: Sidebar

struct LibrarySidebar: View {
    @Environment(AppModel.self) private var model
    @State private var pendingDelete: ProjectSummary?

    var body: some View {
        List(selection: Binding(get: { model.selection }, set: { model.select($0) })) {
            Section("Library") {
                ForEach(model.projects) { item in
                    ProjectRow(item: item)
                        .tag(item.id)
                        .contextMenu {
                            Button("Delete Story…", role: .destructive) { pendingDelete = item }
                                .disabled(model.isBusy(item.id))
                        }
                }
            }
        }
        .listStyle(.sidebar)
        .overlay {
            if model.projects.isEmpty, model.engineState == .running {
                ContentUnavailableView("No stories yet", systemImage: "books.vertical", description: Text("Create your first story below."))
            }
        }
        .safeAreaInset(edge: .bottom) {
            VStack(spacing: 10) {
                Button {
                    model.showNewStory = true
                } label: {
                    Label("New Story", systemImage: "plus")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
                .controlSize(.large)
                .disabled(model.engineState != .running)
                EngineStatusBadge()
            }
            .padding(12)
            .background(.bar)
        }
        .confirmationDialog(
            "Delete “\(pendingDelete?.title ?? "")”?",
            isPresented: Binding(get: { pendingDelete != nil }, set: { if !$0 { pendingDelete = nil } }),
            presenting: pendingDelete
        ) { item in
            Button("Delete Story", role: .destructive) {
                Task { await model.delete(item.id) }
            }
        } message: { _ in
            Text("This removes the story, its art, clips and exports from disk.")
        }
    }
}

struct ProjectRow: View {
    @Environment(AppModel.self) private var model
    var item: ProjectSummary

    var body: some View {
        HStack(spacing: 10) {
            AspectImage(url: model.coverURL(item), ratio: 16 / 11, cornerRadius: 6)
                .frame(width: 64)
            VStack(alignment: .leading, spacing: 3) {
                Text(item.title)
                    .font(.headline)
                    .lineLimit(1)
                HStack(spacing: 4) {
                    Image(systemName: item.format.symbol)
                    Text(item.format.title)
                    if item.shots > 0 {
                        Text("· \(item.shots) panels")
                    }
                }
                .font(.caption)
                .foregroundStyle(.secondary)
            }
            Spacer(minLength: 0)
            if model.isBusy(item.id) {
                ProgressView().controlSize(.small)
            }
        }
        .padding(.vertical, 4)
    }
}

struct EngineStatusBadge: View {
    @Environment(AppModel.self) private var model
    @State private var showInfo = false

    var body: some View {
        Button {
            showInfo.toggle()
        } label: {
            HStack(spacing: 6) {
                Circle().fill(color).frame(width: 8, height: 8)
                Text(label).font(.caption)
                Spacer()
                Image(systemName: "info.circle").font(.caption)
            }
            .foregroundStyle(.secondary)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .popover(isPresented: $showInfo, arrowEdge: .top) {
            EngineInfoView().padding(16).frame(width: 360)
        }
    }

    private var color: Color {
        switch model.engineState {
        case .running: .green
        case .starting, .stopped: .yellow
        case .failed: .red
        }
    }

    private var label: String {
        switch model.engineState {
        case .running: "Engine running · \(model.engineInfo?.profile ?? model.profile)"
        case .starting: "Starting engine…"
        case .stopped: "Engine stopped"
        case .failed: "Engine offline"
        }
    }
}

struct EngineInfoView: View {
    @Environment(AppModel.self) private var model

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("On-device models").font(.headline)
            if let info = model.engineInfo {
                row("Writer", info.llm)
                row("Portraits", info.image)
                row("Panels", info.ref.isEmpty ? info.image : info.ref)
                row("Video", info.video.isEmpty ? "Off" : info.video)
                row("Projects", info.projectsDir)
            } else {
                Text("The engine is not connected.").foregroundStyle(.secondary)
            }
        }
    }

    private func row(_ title: String, _ value: String) -> some View {
        VStack(alignment: .leading, spacing: 1) {
            Text(title).font(.caption).foregroundStyle(.secondary)
            Text(value).font(.callout.monospaced()).textSelection(.enabled).lineLimit(2)
        }
    }
}
#endif
