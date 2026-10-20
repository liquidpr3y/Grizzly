#if os(macOS)
import GrizzlyCore
import SwiftUI

/// First launch: checks this Mac, then downloads the models the profile needs.
struct SetupView: View {
    @Environment(AppModel.self) private var model

    var body: some View {
        if let setup = model.setup {
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    header(setup)
                    HardwarePanel(setup: setup)
                    ModelsPanel(setup: setup)
                    ForEach(setup.notes, id: \.self) { note in
                        Label(note, systemImage: "info.circle")
                            .font(.callout)
                            .foregroundStyle(.secondary)
                    }
                    footer(setup)
                }
                .padding(32)
                .frame(maxWidth: 780)
                .frame(maxWidth: .infinity)
            }
            .background(DotGrid())
        }
    }

    private func header(_ setup: SetupStatus) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Image(systemName: "shippingbox")
                .font(.system(size: 34, weight: .light))
                .foregroundStyle(Theme.accent)
            Text(setup.ready ? "Grizzly is ready" : "Set up Grizzly").font(Theme.titleFont)
            Text(setup.ready
                 ? "Everything a story needs is installed on this Mac."
                 : "Grizzly runs entirely on this Mac. It needs its AI models first: a one-time download of "
                    + "\(formatBytes(setup.remainingBytes())). After that it works offline.")
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
        }
    }

    private func footer(_ setup: SetupStatus) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            if setup.downloading {
                ProgressView(value: setup.requiredFraction)
                    .tint(Theme.accent)
            }
            HStack {
                Text("Models are kept in \(setup.cacheDir), shared with other MLX apps. Interrupted downloads resume.")
                    .font(.caption)
                    .foregroundStyle(.tertiary)
                    .textSelection(.enabled)
                Spacer(minLength: 16)
                if !setup.ready {
                    Button("Skip for Now") { model.showSetup = false }
                }
                primaryButton(setup)
            }
        }
    }

    @ViewBuilder
    private func primaryButton(_ setup: SetupStatus) -> some View {
        if setup.ready {
            Button {
                model.showSetup = false
            } label: {
                Label("Start Creating", systemImage: "sparkles").padding(.horizontal, 6)
            }
            .buttonStyle(.borderedProminent)
            .controlSize(.large)
            .keyboardShortcut(.defaultAction)
        } else if setup.downloading {
            Button {} label: {
                Text("Downloading… \(Int((setup.requiredFraction * 100).rounded()))%")
                    .monospacedDigit()
                    .padding(.horizontal, 6)
            }
            .buttonStyle(.borderedProminent)
            .controlSize(.large)
            .disabled(true)
        } else {
            Button {
                Task { await model.download() }
            } label: {
                Label("Download Models (\(formatBytes(setup.remainingBytes())))", systemImage: "arrow.down.circle")
                    .padding(.horizontal, 6)
            }
            .buttonStyle(.borderedProminent)
            .controlSize(.large)
            .keyboardShortcut(.defaultAction)
            .disabled(!setup.system.supported)
        }
    }
}

private struct HardwarePanel: View {
    @Environment(AppModel.self) private var model
    var setup: SetupStatus

    var body: some View {
        NodePanel(title: "This Mac", symbol: "laptopcomputer", type: .file) {
            if !setup.system.supported {
                Badge(text: "Not supported", symbol: "xmark.octagon.fill", tint: .red)
            }
        } content: {
            VStack(alignment: .leading, spacing: 12) {
                ForEach(setup.system.checks) { check in
                    HStack(alignment: .firstTextBaseline, spacing: 10) {
                        icon(check.status)
                        VStack(alignment: .leading, spacing: 2) {
                            Text(check.label).font(.callout.weight(.medium))
                            Text(check.detail).font(.callout).foregroundStyle(.secondary)
                                .fixedSize(horizontal: false, vertical: true)
                        }
                    }
                }
                if setup.system.recommendedProfile != setup.profile {
                    Divider()
                    HStack {
                        Text("This Mac suits the **\(setup.system.recommendedProfile)** profile (running **\(setup.profile)**).")
                            .font(.callout)
                        Spacer()
                        Button("Switch") { Task { await model.useRecommendedProfile() } }
                            .disabled(setup.downloading)
                    }
                }
            }
            .padding(14)
        }
    }

    @ViewBuilder
    private func icon(_ status: SystemInfo.Check.Status) -> some View {
        switch status {
        case .ok: Image(systemName: "checkmark.circle.fill").foregroundStyle(Theme.accent)
        case .warn: Image(systemName: "exclamationmark.triangle.fill").foregroundStyle(.yellow)
        case .fail: Image(systemName: "xmark.octagon.fill").foregroundStyle(.red)
        }
    }
}

private struct ModelsPanel: View {
    var setup: SetupStatus

    var body: some View {
        NodePanel(title: "Models", symbol: "cpu", type: .image) {
            Text(setup.profile).font(.caption.monospaced()).foregroundStyle(.secondary)
        } content: {
            VStack(spacing: 0) {
                ForEach(Array(setup.models.enumerated()), id: \.element.id) { index, item in
                    if index > 0 { Divider().overlay(Theme.stroke) }
                    ModelRow(item: item)
                }
            }
        }
    }
}

private struct ModelRow: View {
    @Environment(AppModel.self) private var model
    var item: ModelStatus

    var body: some View {
        HStack(alignment: .center, spacing: 14) {
            VStack(alignment: .leading, spacing: 4) {
                HStack(spacing: 6) {
                    Text(item.title).font(.callout.weight(.semibold))
                    if !item.required { Badge(text: "Optional") }
                    if !item.license.isEmpty { Badge(text: item.license) }
                }
                Text(item.purpose).font(.caption).foregroundStyle(.secondary)
                if let error = item.error, item.state == .failed {
                    Text(error).font(.caption).foregroundStyle(.red).lineLimit(2).textSelection(.enabled)
                }
            }
            Spacer(minLength: 12)
            trailing.frame(width: 190, alignment: .trailing)
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 12)
    }

    @ViewBuilder
    private var trailing: some View {
        switch item.state {
        case .done:
            Label("Installed · \(formatBytes(item.sizeBytes))", systemImage: "checkmark.circle.fill")
                .font(.caption)
                .foregroundStyle(Theme.accent)
        case .downloading:
            VStack(alignment: .trailing, spacing: 4) {
                ProgressView(value: item.fraction).tint(Theme.accent)
                Text("\(formatBytes(item.downloadedBytes)) of \(formatBytes(item.sizeBytes))")
                    .font(.caption.monospacedDigit())
                    .foregroundStyle(.secondary)
            }
        case .queued:
            Text("Waiting · \(formatBytes(item.sizeBytes))").font(.caption).foregroundStyle(.secondary)
        case .failed:
            Button("Retry") { Task { await model.download([item.id]) } }
        case .idle:
            if item.required {
                Text(formatBytes(item.remainingBytes)).font(.caption.monospacedDigit()).foregroundStyle(.secondary)
            } else {
                Button("Download \(formatBytes(item.remainingBytes))") { Task { await model.download([item.id]) } }
                    .controlSize(.small)
            }
        }
    }
}
#endif
