#if os(macOS)
import GrizzlyCore
import SwiftUI

/// The project's pipeline as a node graph, after ComfyUI: each stage is a
/// node with typed input and output sockets, wired left to right. Nodes show
/// live status and a preview of their output; clicking one opens its tab.
struct GraphTab: View {
    @Environment(AppModel.self) private var model
    var envelope: ProjectEnvelope
    @Binding var tab: ProjectTab
    @State private var zoom: CGFloat = 0.85
    @State private var gestureStartZoom: CGFloat?
    @State private var fitted = false

    private var project: Project { envelope.project }

    var body: some View {
        GeometryReader { geometry in
            ScrollView([.horizontal, .vertical]) {
                canvas
                    .scaleEffect(zoom, anchor: .topLeading)
                    .frame(width: GraphLayout.canvasSize.width * zoom,
                           height: GraphLayout.canvasSize.height * zoom,
                           alignment: .topLeading)
            }
            .background(Theme.canvas)
            .gesture(
                MagnifyGesture()
                    .onChanged { value in
                        let start = gestureStartZoom ?? zoom
                        gestureStartZoom = start
                        zoom = GraphLayout.clamp(start * value.magnification)
                    }
                    .onEnded { _ in gestureStartZoom = nil }
            )
            .overlay(alignment: .bottomTrailing) {
                zoomControls(fit: GraphLayout.fit(geometry.size))
                    .padding(14)
            }
            .onAppear {
                if !fitted {
                    zoom = GraphLayout.fit(geometry.size)
                    fitted = true
                }
            }
        }
    }

    private var canvas: some View {
        ZStack(alignment: .topLeading) {
            DotGrid()
            ForEach(GraphLayout.edges.indices, id: \.self) { index in
                wire(GraphLayout.edges[index])
            }
            ForEach(GraphLayout.nodes) { spec in
                node(spec)
                    .frame(width: GraphLayout.nodeSize.width, height: GraphLayout.nodeSize.height)
                    .position(x: spec.origin.x + GraphLayout.nodeSize.width / 2,
                              y: spec.origin.y + GraphLayout.nodeSize.height / 2)
            }
        }
        .frame(width: GraphLayout.canvasSize.width, height: GraphLayout.canvasSize.height, alignment: .topLeading)
    }

    // MARK: Wires

    private func wire(_ edge: GraphEdge) -> some View {
        let from = GraphLayout.spec(edge.from)
        let to = GraphLayout.spec(edge.to)
        let start = CGPoint(x: from.origin.x + GraphLayout.nodeSize.width, y: from.origin.y + GraphLayout.portY(edge.output))
        let end = CGPoint(x: to.origin.x, y: to.origin.y + GraphLayout.portY(edge.input))
        let bend = max(50, abs(end.x - start.x) / 2)
        let live = state(of: edge.to) == .running || state(of: edge.from) == .running
        let flowing = state(of: edge.from) == .done
        return Path { path in
            path.move(to: start)
            path.addCurve(to: end,
                          control1: CGPoint(x: start.x + bend, y: start.y),
                          control2: CGPoint(x: end.x - bend, y: end.y))
        }
        .stroke(edge.type.color.opacity(live ? 1 : (flowing ? 0.75 : 0.3)),
                style: StrokeStyle(lineWidth: live ? 3 : 2.2, lineCap: .round, dash: flowing || live ? [] : [6, 5]))
        .shadow(color: live ? edge.type.color.opacity(0.6) : .clear, radius: 6)
    }

    // MARK: Nodes

    enum NodeState { case pending, running, done, optional }

    private var runningNode: GraphNodeID? {
        guard let job = model.job(for: project.id), !job.state.isFinished else { return nil }
        switch job.stage ?? job.step {
        case "bible": return .bible
        case "outline": return .outline
        case "shots": return .storyboard
        case "portraits": return .cast
        case "images": return .panels
        case "video": return .clips
        case "comic", "vn", "animatic": return .exports
        default: return nil
        }
    }

    private func state(of id: GraphNodeID) -> NodeState {
        if runningNode == id { return .running }
        let status = envelope.status
        let exports = model.exports
        let done: Bool = switch id {
        case .premise: true
        case .bible: status.bible
        case .outline: status.outline
        case .storyboard: status.shots
        case .cast: status.portraits
        case .panels: status.images
        case .clips: project.shots.contains { $0.video != nil }
        case .exports: exports.map { $0.comic.pdf != nil || $0.vn.html != nil || $0.animatic.mp4 != nil } ?? false
        }
        if done { return .done }
        return id == .clips ? .optional : .pending
    }

    private func node(_ spec: GraphNodeSpec) -> some View {
        GraphNodeView(spec: spec, state: state(of: spec.id), job: runningNode == spec.id ? model.job(for: project.id) : nil) {
            nodeBody(spec.id)
        }
        .onTapGesture { tab = spec.tab }
    }

    @ViewBuilder
    private func nodeBody(_ id: GraphNodeID) -> some View {
        let bible = project.bible
        switch id {
        case .premise:
            VStack(alignment: .leading, spacing: 8) {
                Badge(text: project.format.title, symbol: project.format.symbol, tint: Theme.accent)
                Text(project.premise)
                    .font(.system(size: 12))
                    .foregroundStyle(.secondary)
                    .lineLimit(6)
            }
        case .bible:
            if let bible {
                VStack(alignment: .leading, spacing: 6) {
                    Text(bible.title).font(.system(size: 13, weight: .semibold)).lineLimit(1)
                    Text(bible.logline).font(.system(size: 11.5)).foregroundStyle(.secondary).lineLimit(4)
                    Text("\(bible.characters.count) characters · \(bible.locations.count) locations")
                        .font(.system(size: 10.5, weight: .medium))
                        .foregroundStyle(.tertiary)
                }
            } else {
                hint("Writes the cast, the world and the art direction.")
            }
        case .outline:
            if let scenes = project.outline?.scenes, !scenes.isEmpty {
                VStack(alignment: .leading, spacing: 5) {
                    ForEach(Array(scenes.prefix(6).enumerated()), id: \.offset) { index, scene in
                        HStack(spacing: 6) {
                            Text("\(index + 1)")
                                .font(.system(size: 10, weight: .bold).monospacedDigit())
                                .foregroundStyle(Theme.typeText)
                                .frame(width: 14)
                            Text(scene.title).font(.system(size: 11.5)).lineLimit(1)
                        }
                    }
                }
            } else {
                hint("Breaks the story into scenes.")
            }
        case .storyboard:
            if !project.shots.isEmpty {
                VStack(alignment: .leading, spacing: 8) {
                    HStack(alignment: .firstTextBaseline, spacing: 4) {
                        Text("\(project.shots.count)").font(.system(size: 28, weight: .semibold).monospacedDigit())
                        Text("shots").foregroundStyle(.secondary)
                    }
                    HStack(spacing: 5) {
                        ForEach(Framing.allCases) { framing in
                            let count = project.shots.filter { $0.framing == framing }.count
                            if count > 0 { Badge(text: "\(count) \(framing.title.lowercased())") }
                        }
                    }
                    Text("\(project.shots.filter { !$0.dialogue.isEmpty }.count) with dialogue")
                        .font(.system(size: 10.5, weight: .medium))
                        .foregroundStyle(.tertiary)
                }
            } else {
                hint("Turns each scene into shots with framing and dialogue.")
            }
        case .cast:
            if let bible, !bible.characters.isEmpty {
                HStack(alignment: .top, spacing: 8) {
                    ForEach(bible.characters.prefix(4)) { character in
                        VStack(spacing: 4) {
                            AspectImage(url: character.portrait.flatMap { model.fileURL($0) }, ratio: 896 / 1152, cornerRadius: 5)
                            Text(character.name)
                                .font(.system(size: 9.5, weight: .medium))
                                .lineLimit(1)
                        }
                    }
                }
            } else {
                hint("Draws a reference portrait for every character.")
            }
        case .panels:
            let drawn = project.shots.filter { $0.image != nil }
            if !drawn.isEmpty {
                VStack(alignment: .leading, spacing: 6) {
                    LazyVGrid(columns: Array(repeating: GridItem(.flexible(), spacing: 4), count: 3), spacing: 4) {
                        ForEach(drawn.prefix(6)) { shot in
                            AspectImage(url: shot.image.flatMap { model.fileURL($0) }, ratio: 16 / 10, cornerRadius: 3)
                        }
                    }
                    Text("\(drawn.count) of \(project.shots.count) drawn")
                        .font(.system(size: 10.5, weight: .medium))
                        .foregroundStyle(.tertiary)
                }
            } else {
                hint("Draws every shot from the cast portraits.")
            }
        case .clips:
            let animated = project.shots.filter { $0.video != nil }
            if let first = animated.first {
                VStack(alignment: .leading, spacing: 6) {
                    AspectImage(url: first.image.flatMap { model.fileURL($0) }, ratio: 16 / 9, cornerRadius: 5)
                        .overlay { Image(systemName: "play.circle.fill").font(.title).foregroundStyle(.white.opacity(0.85)) }
                    Text("\(animated.count) animated shot\(animated.count == 1 ? "" : "s")")
                        .font(.system(size: 10.5, weight: .medium))
                        .foregroundStyle(.tertiary)
                }
            } else {
                hint("Optional. Animate chosen shots from the Storyboard; each clip takes minutes.")
            }
        case .exports:
            VStack(alignment: .leading, spacing: 8) {
                exportRow("Comic", "book.pages", model.exports?.comic.pdf)
                exportRow("Visual novel", "text.bubble", model.exports?.vn.html)
                exportRow("Animatic", "film", model.exports?.animatic.mp4)
            }
        }
    }

    private func hint(_ text: String) -> some View {
        Text(text)
            .font(.system(size: 11.5))
            .foregroundStyle(.tertiary)
            .fixedSize(horizontal: false, vertical: true)
    }

    private func exportRow(_ title: String, _ symbol: String, _ path: String?) -> some View {
        HStack(spacing: 8) {
            Circle()
                .fill(path == nil ? Theme.stroke : Theme.typeFile)
                .frame(width: 7, height: 7)
            Image(systemName: symbol).font(.system(size: 11)).foregroundStyle(.secondary).frame(width: 16)
            Text(title).font(.system(size: 12))
            Spacer()
            if path != nil {
                Button("Open") { model.open(path) }
                    .buttonStyle(.borderless)
                    .font(.system(size: 11, weight: .semibold))
                    .foregroundStyle(Theme.typeFile)
            } else {
                Text("—").foregroundStyle(.tertiary)
            }
        }
    }

    // MARK: Zoom

    private func zoomControls(fit: CGFloat) -> some View {
        HStack(spacing: 0) {
            zoomButton("minus.magnifyingglass") { zoom = GraphLayout.clamp(zoom - 0.1) }
            Divider().frame(height: 18)
            Button { zoom = fit } label: {
                Text("\(Int((zoom * 100).rounded()))%")
                    .font(.system(size: 11, weight: .medium).monospacedDigit())
                    .frame(width: 46, height: 28)
            }
            .buttonStyle(.plain)
            .help("Fit to window")
            Divider().frame(height: 18)
            zoomButton("plus.magnifyingglass") { zoom = GraphLayout.clamp(zoom + 0.1) }
        }
        .background(Theme.nodeHeader, in: RoundedRectangle(cornerRadius: 8))
        .overlay(RoundedRectangle(cornerRadius: 8).strokeBorder(Theme.stroke))
    }

    private func zoomButton(_ symbol: String, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Image(systemName: symbol).frame(width: 32, height: 28)
        }
        .buttonStyle(.plain)
    }
}

// MARK: Layout

enum GraphNodeID: Hashable {
    case premise, bible, outline, storyboard, cast, panels, clips, exports
}

struct GraphPort {
    var label: String
    var type: PortType
}

struct GraphNodeSpec: Identifiable {
    var id: GraphNodeID
    var title: String
    var symbol: String
    var column: CGFloat
    var row: CGFloat
    var inputs: [GraphPort]
    var outputs: [GraphPort]
    var tab: ProjectTab

    var origin: CGPoint { GraphLayout.origin(column: column, row: row) }
}

struct GraphEdge {
    var from: GraphNodeID
    var output: Int
    var to: GraphNodeID
    var input: Int
    var type: PortType
}

enum GraphLayout {
    static let nodeSize = CGSize(width: 220, height: 232)
    static let gap = CGSize(width: 64, height: 56)
    static let margin: CGFloat = 36
    static let portRow: CGFloat = 20

    static let nodes: [GraphNodeSpec] = [
        GraphNodeSpec(id: .premise, title: "Premise", symbol: "lightbulb", column: 0, row: 0,
                      inputs: [], outputs: [GraphPort(label: "idea", type: .text)], tab: .story),
        GraphNodeSpec(id: .bible, title: "Story Bible", symbol: "text.book.closed", column: 1, row: 0,
                      inputs: [GraphPort(label: "idea", type: .text)],
                      outputs: [GraphPort(label: "bible", type: .text)], tab: .story),
        GraphNodeSpec(id: .outline, title: "Outline", symbol: "list.number", column: 2, row: 0,
                      inputs: [GraphPort(label: "bible", type: .text)],
                      outputs: [GraphPort(label: "scenes", type: .text)], tab: .story),
        GraphNodeSpec(id: .cast, title: "Cast", symbol: "person.2", column: 2, row: 1,
                      inputs: [GraphPort(label: "bible", type: .text)],
                      outputs: [GraphPort(label: "portraits", type: .image)], tab: .cast),
        GraphNodeSpec(id: .storyboard, title: "Storyboard", symbol: "rectangle.split.3x3", column: 3, row: 0,
                      inputs: [GraphPort(label: "scenes", type: .text)],
                      outputs: [GraphPort(label: "shots", type: .text)], tab: .storyboard),
        GraphNodeSpec(id: .panels, title: "Panels", symbol: "photo.on.rectangle.angled", column: 4, row: 0.5,
                      inputs: [GraphPort(label: "shots", type: .text), GraphPort(label: "portraits", type: .image)],
                      outputs: [GraphPort(label: "panels", type: .image)], tab: .storyboard),
        GraphNodeSpec(id: .clips, title: "Clips", symbol: "film.stack", column: 5, row: 0,
                      inputs: [GraphPort(label: "panels", type: .image)],
                      outputs: [GraphPort(label: "clips", type: .video)], tab: .storyboard),
        GraphNodeSpec(id: .exports, title: "Exports", symbol: "square.and.arrow.up", column: 5, row: 1,
                      inputs: [GraphPort(label: "panels", type: .image), GraphPort(label: "clips", type: .video)],
                      outputs: [GraphPort(label: "files", type: .file)], tab: .export),
    ]

    static let edges: [GraphEdge] = [
        GraphEdge(from: .premise, output: 0, to: .bible, input: 0, type: .text),
        GraphEdge(from: .bible, output: 0, to: .outline, input: 0, type: .text),
        GraphEdge(from: .bible, output: 0, to: .cast, input: 0, type: .text),
        GraphEdge(from: .outline, output: 0, to: .storyboard, input: 0, type: .text),
        GraphEdge(from: .storyboard, output: 0, to: .panels, input: 0, type: .text),
        GraphEdge(from: .cast, output: 0, to: .panels, input: 1, type: .image),
        GraphEdge(from: .panels, output: 0, to: .clips, input: 0, type: .image),
        GraphEdge(from: .panels, output: 0, to: .exports, input: 0, type: .image),
        GraphEdge(from: .clips, output: 0, to: .exports, input: 1, type: .video),
    ]

    static var canvasSize: CGSize {
        let columns = (nodes.map(\.column).max() ?? 0) + 1
        let rows = (nodes.map(\.row).max() ?? 0) + 1
        return CGSize(width: margin * 2 + columns * nodeSize.width + (columns - 1) * gap.width,
                      height: margin * 2 + rows * nodeSize.height + (rows - 1) * gap.height)
    }

    static func origin(column: CGFloat, row: CGFloat) -> CGPoint {
        CGPoint(x: margin + column * (nodeSize.width + gap.width), y: margin + row * (nodeSize.height + gap.height))
    }

    /// Vertical centre of the i-th socket row, measured from the node's top.
    static func portY(_ index: Int) -> CGFloat {
        Theme.headerHeight + 4 + portRow * (CGFloat(index) + 0.5)
    }

    static func spec(_ id: GraphNodeID) -> GraphNodeSpec { nodes.first { $0.id == id }! }

    static func clamp(_ zoom: CGFloat) -> CGFloat { min(1.6, max(0.4, zoom)) }

    /// Zoom that fits the graph, but never so small that text is unreadable.
    static func fit(_ size: CGSize) -> CGFloat {
        let scale = min((size.width - 24) / canvasSize.width, (size.height - 24) / canvasSize.height)
        return clamp(min(1, max(0.7, scale)))
    }
}

// MARK: Node view

struct GraphNodeView<Content: View>: View {
    var spec: GraphNodeSpec
    var state: GraphTab.NodeState
    var job: Job?
    @ViewBuilder var content: () -> Content
    @State private var hovering = false

    private var rows: Int { max(spec.inputs.count, spec.outputs.count) }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            header
            ports
            content()
                .padding(.horizontal, 12)
                .padding(.vertical, 8)
                .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
            if let job, state == .running {
                footer(job)
            }
        }
        .frame(width: GraphLayout.nodeSize.width, height: GraphLayout.nodeSize.height)
        .background(hovering ? Theme.nodeHover : Theme.node)
        .clipShape(RoundedRectangle(cornerRadius: Theme.corner, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: Theme.corner, style: .continuous)
                .strokeBorder(state == .running ? Theme.accent : (hovering ? Theme.accent.opacity(0.5) : Theme.stroke),
                              lineWidth: state == .running ? 2 : 1)
        )
        .overlay(alignment: .topLeading) { sockets }
        .shadow(color: state == .running ? Theme.accent.opacity(0.35) : .black.opacity(0.4), radius: state == .running ? 14 : 8, y: 4)
        .opacity(state == .pending ? 0.75 : 1)
        .contentShape(Rectangle())
        .onHover { hovering = $0 }
        .animation(.easeOut(duration: 0.15), value: hovering)
        .help("Open \(spec.tab.rawValue)")
    }

    private var header: some View {
        HStack(spacing: 7) {
            Image(systemName: spec.symbol)
                .font(.system(size: 11, weight: .semibold))
                .foregroundStyle(state == .done ? Theme.accent : .secondary)
            Text(spec.title)
                .font(.system(size: 12.5, weight: .semibold))
            Spacer()
            switch state {
            case .done:
                Image(systemName: "checkmark.circle.fill").foregroundStyle(Theme.accent)
            case .running:
                ProgressView().controlSize(.mini)
            case .pending:
                Image(systemName: "circle.dashed").foregroundStyle(.tertiary)
            case .optional:
                Text("optional").font(.system(size: 9.5, weight: .medium)).foregroundStyle(.tertiary)
            }
        }
        .font(.system(size: 12))
        .padding(.horizontal, 10)
        .frame(height: Theme.headerHeight)
        .background(Theme.nodeHeader)
    }

    private var ports: some View {
        VStack(spacing: 0) {
            ForEach(0..<rows, id: \.self) { index in
                HStack {
                    if index < spec.inputs.count {
                        Text(spec.inputs[index].label)
                    }
                    Spacer()
                    if index < spec.outputs.count {
                        Text(spec.outputs[index].label)
                    }
                }
                .font(.system(size: 10, weight: .medium))
                .foregroundStyle(.secondary)
                .padding(.horizontal, 12)
                .frame(height: GraphLayout.portRow)
            }
        }
        .padding(.top, 4)
    }

    /// Sockets sit on the node's edges, where the wires attach.
    private var sockets: some View {
        ZStack(alignment: .topLeading) {
            ForEach(spec.inputs.indices, id: \.self) { index in
                socket(spec.inputs[index].type)
                    .position(x: 0, y: GraphLayout.portY(index))
            }
            ForEach(spec.outputs.indices, id: \.self) { index in
                socket(spec.outputs[index].type)
                    .position(x: GraphLayout.nodeSize.width, y: GraphLayout.portY(index))
            }
        }
        .frame(width: GraphLayout.nodeSize.width, height: GraphLayout.nodeSize.height, alignment: .topLeading)
        .allowsHitTesting(false)
    }

    private func socket(_ type: PortType) -> some View {
        Circle()
            .fill(type.color)
            .frame(width: 10, height: 10)
            .overlay(Circle().strokeBorder(Theme.canvas, lineWidth: 2))
    }

    private func footer(_ job: Job) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            if let fraction = job.fraction {
                ProgressView(value: Double(fraction.done - 1), total: Double(fraction.total))
                    .tint(Theme.accent)
                Text("\(fraction.done) of \(fraction.total) · \(job.progressLabel)")
            } else {
                Text(job.state == .queued ? "Queued…" : "Working…")
            }
        }
        .font(.system(size: 10, weight: .medium))
        .foregroundStyle(.secondary)
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
        .background(Theme.nodeHeader)
    }
}
#endif
