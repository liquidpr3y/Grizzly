#if os(macOS)
import GrizzlyCore
import SwiftUI

/// Node-editor look (after ComfyUI): graphite canvas with a dot grid, nodes
/// with title bars and typed sockets, wires coloured by the data they carry.
/// Neutral greys with a teal accent.
enum Theme {
    static let canvas = Color(red: 0.071, green: 0.078, blue: 0.090)
    static let panel = Color(red: 0.094, green: 0.106, blue: 0.125)
    static let node = Color(red: 0.125, green: 0.141, blue: 0.169)
    static let nodeHover = Color(red: 0.149, green: 0.165, blue: 0.196)
    static let nodeHeader = Color(red: 0.157, green: 0.176, blue: 0.208)
    static let stroke = Color(red: 0.204, green: 0.227, blue: 0.267)
    static let gridDot = Color(red: 0.169, green: 0.188, blue: 0.220)

    static let accent = Color(red: 0.204, green: 0.776, blue: 0.690)

    // Data types, used for sockets, wires and type chips.
    static let typeText = Color(red: 0.416, green: 0.663, blue: 1.0)
    static let typeImage = accent
    static let typeVideo = Color(red: 0.643, green: 0.545, blue: 0.98)
    static let typeFile = Color(red: 0.608, green: 0.827, blue: 0.416)

    // Kept for existing call sites.
    static let surface = node
    static let surfaceHover = nodeHover

    static let corner: CGFloat = 10
    static let headerHeight: CGFloat = 30
    static let titleFont = Font.system(size: 26, weight: .semibold, design: .default)
}

enum PortType {
    case text, image, video, file

    var color: Color {
        switch self {
        case .text: Theme.typeText
        case .image: Theme.typeImage
        case .video: Theme.typeVideo
        case .file: Theme.typeFile
        }
    }
}

extension StoryFormat {
    var symbol: String {
        switch self {
        case .comic: "book.pages"
        case .vn: "text.bubble"
        case .film: "film"
        }
    }

    var blurb: String {
        switch self {
        case .comic: "Laid-out pages with captions and speech bubbles."
        case .vn: "Click-through scenes with dialogue, plus a Ren'Py project."
        case .film: "Widescreen shots, voice-over and animated clips."
        }
    }
}

/// Node surface used across the app.
struct CardBackground: ViewModifier {
    var highlighted = false
    var selected = false

    func body(content: Content) -> some View {
        content
            .background(
                RoundedRectangle(cornerRadius: Theme.corner, style: .continuous)
                    .fill(highlighted ? Theme.nodeHover : Theme.node)
            )
            .overlay(
                RoundedRectangle(cornerRadius: Theme.corner, style: .continuous)
                    .strokeBorder(selected ? Theme.accent : Theme.stroke, lineWidth: selected ? 2 : 1)
            )
            .shadow(color: selected ? Theme.accent.opacity(0.25) : .black.opacity(0.3), radius: selected ? 10 : 6, y: 3)
    }
}

extension View {
    func card(highlighted: Bool = false, selected: Bool = false) -> some View {
        modifier(CardBackground(highlighted: highlighted, selected: selected))
    }
}

/// A node: title bar with a typed socket and optional accessory, then content.
struct NodePanel<Accessory: View, Content: View>: View {
    var title: String
    var symbol: String
    var type: PortType
    var highlighted = false
    var selected = false
    @ViewBuilder var accessory: () -> Accessory
    @ViewBuilder var content: () -> Content

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack(spacing: 8) {
                Circle()
                    .fill(type.color)
                    .frame(width: 8, height: 8)
                Image(systemName: symbol)
                    .font(.system(size: 11, weight: .semibold))
                    .foregroundStyle(.secondary)
                Text(title)
                    .font(.system(size: 12, weight: .semibold))
                    .lineLimit(1)
                Spacer(minLength: 4)
                accessory()
            }
            .padding(.horizontal, 10)
            .frame(height: Theme.headerHeight)
            .background(Theme.nodeHeader)
            content()
        }
        .clipShape(RoundedRectangle(cornerRadius: Theme.corner, style: .continuous))
        .card(highlighted: highlighted, selected: selected)
    }
}

extension NodePanel where Accessory == EmptyView {
    init(title: String, symbol: String, type: PortType, highlighted: Bool = false, selected: Bool = false,
         @ViewBuilder content: @escaping () -> Content) {
        self.init(title: title, symbol: symbol, type: type, highlighted: highlighted, selected: selected,
                  accessory: { EmptyView() }, content: content)
    }
}

/// Small pill label.
struct Badge: View {
    var text: String
    var symbol: String?
    var tint: Color = .secondary

    var body: some View {
        HStack(spacing: 4) {
            if let symbol { Image(systemName: symbol) }
            Text(text)
        }
        .font(.system(size: 10, weight: .semibold))
        .padding(.horizontal, 7)
        .padding(.vertical, 3)
        .foregroundStyle(tint)
        .background(Color.black.opacity(0.45), in: Capsule())
        .overlay(Capsule().strokeBorder(Theme.stroke, lineWidth: 1))
    }
}

/// Dot grid canvas background.
struct DotGrid: View {
    var spacing: CGFloat = 22

    var body: some View {
        Canvas { context, size in
            var x: CGFloat = spacing / 2
            while x < size.width {
                var y: CGFloat = spacing / 2
                while y < size.height {
                    context.fill(Path(ellipseIn: CGRect(x: x - 1, y: y - 1, width: 2, height: 2)), with: .color(Theme.gridDot))
                    y += spacing
                }
                x += spacing
            }
        }
        .background(Theme.canvas)
    }
}

/// A remote image cropped to a fixed aspect ratio, with placeholders.
struct AspectImage: View {
    var url: URL?
    var ratio: CGFloat
    var cornerRadius: CGFloat = 6

    var body: some View {
        Color.clear
            .aspectRatio(ratio, contentMode: .fit)
            .overlay {
                AsyncImage(url: url, transaction: Transaction(animation: .easeOut(duration: 0.25))) { phase in
                    switch phase {
                    case let .success(image):
                        image.resizable().scaledToFill()
                    case .failure:
                        Placeholder(symbol: "exclamationmark.triangle")
                    case .empty:
                        if url == nil {
                            Placeholder(symbol: "photo")
                        } else {
                            ZStack {
                                Placeholder(symbol: nil)
                                ProgressView().controlSize(.small)
                            }
                        }
                    @unknown default:
                        Placeholder(symbol: "photo")
                    }
                }
            }
            .clipShape(RoundedRectangle(cornerRadius: cornerRadius, style: .continuous))
    }
}

struct Placeholder: View {
    var symbol: String?

    var body: some View {
        ZStack {
            Rectangle().fill(Theme.canvas)
            if let symbol {
                Image(systemName: symbol)
                    .font(.title3)
                    .foregroundStyle(.tertiary)
            }
        }
    }
}

/// Section title used inside tabs.
struct SectionTitle: View {
    var title: String
    var subtitle: String?

    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(title).font(.system(size: 18, weight: .semibold))
            if let subtitle {
                Text(subtitle).font(.callout).foregroundStyle(.secondary)
            }
        }
    }
}
#endif
