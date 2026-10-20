#if os(macOS)
import GrizzlyCore
import SwiftUI

enum Theme {
    /// Warm amber accent, picked to sit well on the dark studio background.
    static let accent = Color(red: 0.96, green: 0.58, blue: 0.27)
    static let surface = Color.white.opacity(0.045)
    static let surfaceHover = Color.white.opacity(0.075)
    static let stroke = Color.white.opacity(0.09)
    static let corner: CGFloat = 14
    static let titleFont = Font.system(size: 28, weight: .bold, design: .serif)
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

/// Rounded "card" surface used across the app.
struct CardBackground: ViewModifier {
    var highlighted = false
    var selected = false

    func body(content: Content) -> some View {
        content
            .background(
                RoundedRectangle(cornerRadius: Theme.corner, style: .continuous)
                    .fill(highlighted || selected ? Theme.surfaceHover : Theme.surface)
            )
            .overlay(
                RoundedRectangle(cornerRadius: Theme.corner, style: .continuous)
                    .strokeBorder(selected ? Theme.accent : Theme.stroke, lineWidth: selected ? 2 : 1)
            )
    }
}

extension View {
    func card(highlighted: Bool = false, selected: Bool = false) -> some View {
        modifier(CardBackground(highlighted: highlighted, selected: selected))
    }
}

/// Small pill label.
struct Badge: View {
    var text: String
    var symbol: String?
    var tint: Color = .white

    var body: some View {
        HStack(spacing: 4) {
            if let symbol { Image(systemName: symbol) }
            Text(text)
        }
        .font(.caption2.weight(.semibold))
        .padding(.horizontal, 7)
        .padding(.vertical, 3)
        .foregroundStyle(tint)
        .background(.black.opacity(0.55), in: Capsule())
    }
}

/// A remote image cropped to a fixed aspect ratio, with placeholders.
struct AspectImage: View {
    var url: URL?
    var ratio: CGFloat
    var cornerRadius: CGFloat = 10

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
            Rectangle().fill(Color.white.opacity(0.05))
            if let symbol {
                Image(systemName: symbol)
                    .font(.title2)
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
            Text(title).font(.title2.weight(.semibold))
            if let subtitle {
                Text(subtitle).font(.callout).foregroundStyle(.secondary)
            }
        }
    }
}
#endif
