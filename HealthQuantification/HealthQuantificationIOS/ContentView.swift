import Foundation
import SwiftUI
import Observation

extension Color {
    static let ideBackground = Color(red: 0.06, green: 0.07, blue: 0.09)
    static let idePanel = Color(red: 0.10, green: 0.11, blue: 0.14)
    static let idePanelElevated = Color(red: 0.13, green: 0.14, blue: 0.18)
    static let ideBorder = Color.white.opacity(0.08)
    static let ideTextPrimary = Color(red: 0.92, green: 0.94, blue: 0.97)
    static let ideTextSecondary = Color(red: 0.64, green: 0.68, blue: 0.74)
    static let ideTextMuted = Color(red: 0.47, green: 0.51, blue: 0.57)
    static let ideAccent = Color(red: 0.29, green: 0.82, blue: 0.49)
    static let ideAccentMuted = Color(red: 0.18, green: 0.30, blue: 0.23)
    static let ideWarning = Color(red: 0.95, green: 0.71, blue: 0.28)
    static let ideError = Color(red: 0.94, green: 0.40, blue: 0.40)
    static let ideInfo = Color(red: 0.36, green: 0.66, blue: 0.96)
}

struct ContentView: View {
    @Bindable var model: HealthKitService
    @Binding var serverURL: String
    @Binding var exportAllDeepLinkTrigger: Int

    @State private var isExporting = false
    @State private var exportStatusTitle = "Idle"
    @State private var exportStatusDetail = "Waiting for a command."
    @State private var exportStatusTone: ExportStatusTone = .neutral
    @State private var activeAction: String? = nil

    private let ingestClient = IngestClient()

    var body: some View {
        ZStack {
            LinearGradient(
                colors: [.black, .ideBackground, .idePanel],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
            .ignoresSafeArea()

            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    header
                    serverCard
                    diagnosticsCard
                    actionsCard
                    statusCard
                    logCard
                }
                .padding(.horizontal, 16)
                .padding(.top, 18)
                .padding(.bottom, 28)
            }
        }
        .task {
            model.runDoctor()
        }
        .onChange(of: exportAllDeepLinkTrigger) { _, _ in
            triggerExportAll()
        }
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: 8) {
                    Text("Health Quantification")
                        .font(.system(size: 30, weight: .semibold, design: .rounded))
                        .foregroundColor(.ideTextPrimary)

                    Text("Apple Health ingestion console")
                        .font(.system(size: 15, weight: .medium, design: .default))
                        .foregroundColor(.ideTextSecondary)
                }

                Spacer(minLength: 12)

                VStack(alignment: .trailing, spacing: 8) {
                    StatusPill(
                        label: exportStatusTitle.uppercased(),
                        tone: exportStatusTone,
                        icon: exportStatusTone.icon
                    )

                    Text("pipeline://ios → backend")
                        .font(.system(size: 12, weight: .medium, design: .monospaced))
                        .foregroundColor(.ideTextMuted)
                }
            }

            HStack(spacing: 8) {
                headerChip(title: "workspace", value: "ios")
                headerChip(title: "mode", value: "ingest")
                headerChip(title: "window", value: "30d")
            }
        }
    }

    private var serverCard: some View {
        IDECard(title: "Server", subtitle: "Backend endpoint used for HealthKit export") {
            VStack(alignment: .leading, spacing: 10) {
                Text("Server URL")
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundColor(.ideTextSecondary)

                TextField("http://100.x.x.x:7996", text: $serverURL)
                    .autocorrectionDisabled()
                    .font(.system(size: 15, weight: .medium, design: .monospaced))
                    .foregroundColor(.ideTextPrimary)
                    .padding(.horizontal, 14)
                    .padding(.vertical, 14)
                    .background(
                        RoundedRectangle(cornerRadius: 14, style: .continuous)
                            .fill(Color.ideBackground.opacity(0.95))
                            .overlay(
                                RoundedRectangle(cornerRadius: 14, style: .continuous)
                                    .stroke(Color.ideBorder, lineWidth: 1)
                            )
                    )
                    .accessibilityIdentifier("serverURLField")

                Text("Use your Mac or Tailscale address instead of localhost when exporting from iPhone.")
                    .font(.system(size: 12, weight: .medium))
                    .foregroundColor(.ideTextMuted)
            }
        }
    }

    private var diagnosticsCard: some View {
        IDECard(title: "Diagnostics", subtitle: "Current device and authorization state") {
            VStack(spacing: 12) {
                DiagnosticRow(
                    label: "Health data",
                    value: model.healthDataAvailableText == "true" ? "Available" : "Unavailable",
                    tone: model.healthDataAvailableText == "true" ? .success : .failure,
                    accessibilityIdentifier: "healthDataAvailableLabel"
                )
                DiagnosticRow(
                    label: "Authorization",
                    value: model.authorizationState,
                    tone: model.authorizationState.localizedCaseInsensitiveContains("authorized") ? .success : .partial,
                    accessibilityIdentifier: "authorizationStateLabel"
                )
                DiagnosticRow(
                    label: "Last updated",
                    value: model.lastUpdated,
                    tone: .neutral,
                    accessibilityIdentifier: nil
                )
            }
        }
    }

    private var actionsCard: some View {
        IDECard(title: "Actions", subtitle: "Primary controls for device checks and export") {
            VStack(spacing: 12) {
                ActionButton(
                    title: "Run Doctor",
                    subtitle: "Refresh local diagnostics and service state",
                    icon: "stethoscope",
                    style: .secondary,
                    isPressed: activeAction == "doctor",
                    isDisabled: false
                ) {
                    activeAction = "doctor"
                    model.runDoctor()
                    DispatchQueue.main.asyncAfter(deadline: .now() + 0.2) { activeAction = nil }
                }
                .accessibilityIdentifier("runDoctorButton")

                ActionButton(
                    title: "Request Health Access",
                    subtitle: "Open HealthKit permission flow on device",
                    icon: "heart.text.square",
                    style: .secondary,
                    isPressed: activeAction == "access",
                    isDisabled: false
                ) {
                    activeAction = "access"
                    model.requestHealthAccess()
                    DispatchQueue.main.asyncAfter(deadline: .now() + 0.2) { activeAction = nil }
                }
                .accessibilityIdentifier("requestHealthAccessButton")

                ActionButton(
                    title: isExporting ? "Exporting 30-Day Snapshot" : "Export All Data",
                    subtitle: isExporting ? "Collecting and uploading sleep, vitals, body, lifestyle, activity, and workout samples" : "Send the last 30 days of samples to the configured backend",
                    icon: isExporting ? "arrow.triangle.2.circlepath" : "square.and.arrow.up",
                    style: .primary,
                    isPressed: isExporting,
                    isDisabled: isExporting
                ) {
                    triggerExportAll()
                }
                .accessibilityIdentifier("exportAllButton")
            }
        }
    }

    private var statusCard: some View {
        IDECard(title: "Export Status", subtitle: "Pipeline state and latest result") {
            VStack(alignment: .leading, spacing: 12) {
                HStack(alignment: .center, spacing: 10) {
                    Circle()
                        .fill(exportStatusTone.color)
                        .frame(width: 10, height: 10)

                    Text(exportStatusTitle)
                        .font(.system(size: 17, weight: .semibold))
                        .foregroundColor(.ideTextPrimary)
                        .accessibilityIdentifier("exportStatusTitle")

                    Spacer()
                }

                Text(exportStatusDetail)
                    .font(.system(size: 13, weight: .medium, design: .monospaced))
                    .foregroundStyle(exportStatusTone.detailColor)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(14)
                    .background(
                        RoundedRectangle(cornerRadius: 14, style: .continuous)
                            .fill(Color.ideBackground.opacity(0.96))
                            .overlay(
                                RoundedRectangle(cornerRadius: 14, style: .continuous)
                                    .stroke(exportStatusTone.color.opacity(0.28), lineWidth: 1)
                            )
                    )
                    .accessibilityIdentifier("exportStatusDetail")
            }
        }
    }

    private var logCard: some View {
        IDECard(title: "system.log", subtitle: "Streaming service output") {
            ScrollViewReader { proxy in
                ScrollView {
                    LogConsoleContent(lines: logLines)
                }
                .frame(minHeight: 220, maxHeight: 280)
                .background(
                    RoundedRectangle(cornerRadius: 16, style: .continuous)
                        .fill(Color.ideBackground.opacity(0.98))
                        .overlay(
                            RoundedRectangle(cornerRadius: 16, style: .continuous)
                                .stroke(Color.ideBorder, lineWidth: 1)
                        )
                )
                .onChange(of: model.logText) { _, _ in
                    withAnimation(.easeOut(duration: 0.2)) {
                        proxy.scrollTo("bottom", anchor: .bottom)
                    }
                }
            }
        }
    }

    private var logLines: [String] {
        model.logText
            .split(separator: "\n", omittingEmptySubsequences: false)
            .map(String.init)
    }

    private func headerChip(title: String, value: String) -> some View {
        HStack(spacing: 6) {
            Text(title.uppercased())
                .font(.system(size: 10, weight: .medium, design: .monospaced))
                .foregroundColor(.ideTextMuted)

            Text(value)
                .font(.system(size: 10, weight: .medium, design: .monospaced))
                .foregroundColor(.ideTextMuted.opacity(0.9))
        }
        .padding(.horizontal, 8)
        .padding(.vertical, 5)
        .background(
            Capsule(style: .continuous)
                .fill(Color.idePanel.opacity(0.52))
                .overlay(
                    Capsule(style: .continuous)
                        .stroke(Color.ideBorder.opacity(0.35), lineWidth: 1)
                )
        )
    }

    @MainActor
    private func triggerExportAll() {
        guard !isExporting else {
            return
        }

        Task {
            await exportAll()
        }
    }

    @MainActor
    private func exportAll() async {
        guard let exportContext = makeExportContext() else {
            return
        }

        isExporting = true
        exportStatusTitle = "Exporting"
        exportStatusDetail = "Fetching sleep, vitals, body, lifestyle, activity, and workout samples from the last 30 days and sending them to \(exportContext.trimmedURL)."
        exportStatusTone = .neutral

        var resultLines: [String] = []
        var hadFailure = false
        var hadSuccess = false

        do {
            let samples = try await model.fetchSleepSamples(days: 30)
            let response = try await ingestClient.ingestSleep(serverURL: exportContext.url, samples: samples)
            resultLines.append("[sleep] sent \(samples.count), upserted \(response.upserted)")
            hadSuccess = true
        } catch {
            resultLines.append("[sleep] failed: \(error.localizedDescription)")
            hadFailure = true
        }

        do {
            let samples = try await model.fetchVitalsSamples(days: 30)
            let response = try await ingestClient.ingestVitals(serverURL: exportContext.url, samples: samples)
            resultLines.append("[vitals] sent \(samples.count), upserted \(response.upserted)")
            hadSuccess = true
        } catch {
            resultLines.append("[vitals] failed: \(error.localizedDescription)")
            hadFailure = true
        }

        do {
            let samples = try await model.fetchBodySamples(days: 30)
            if samples.isEmpty {
                resultLines.append("[body] no data")
            } else {
                let response = try await ingestClient.ingestBody(serverURL: exportContext.url, samples: samples)
                resultLines.append("[body] sent \(samples.count), upserted \(response.upserted)")
                hadSuccess = true
            }
        } catch {
            resultLines.append("[body] failed: \(error.localizedDescription)")
            hadFailure = true
        }

        do {
            let samples = try await model.fetchLifestyleSamples(days: 30)
            if samples.isEmpty {
                resultLines.append("[lifestyle] no data")
            } else {
                let response = try await ingestClient.ingestLifestyle(serverURL: exportContext.url, samples: samples)
                resultLines.append("[lifestyle] sent \(samples.count), upserted \(response.upserted)")
                hadSuccess = true
            }
        } catch {
            resultLines.append("[lifestyle] failed: \(error.localizedDescription)")
            hadFailure = true
        }

        do {
            let samples = try await model.fetchActivitySamples(days: 30)
            let response = try await ingestClient.ingestActivity(serverURL: exportContext.url, samples: samples)
            resultLines.append("[activity] sent \(samples.count), upserted \(response.upserted)")
            hadSuccess = true
        } catch {
            resultLines.append("[activity] failed: \(error.localizedDescription)")
            hadFailure = true
        }

        do {
            let samples = try await model.fetchWorkoutSamples(days: 30)
            let response = try await ingestClient.ingestWorkouts(serverURL: exportContext.url, samples: samples)
            resultLines.append("[workouts] sent \(samples.count), upserted \(response.upserted)")
            hadSuccess = true
        } catch {
            resultLines.append("[workouts] failed: \(error.localizedDescription)")
            hadFailure = true
        }

        if hadSuccess && hadFailure {
            exportStatusTitle = "Partial"
            exportStatusTone = .partial
        } else if hadSuccess {
            exportStatusTitle = "Success"
            exportStatusTone = .success
        } else {
            exportStatusTitle = "Failed"
            exportStatusTone = .failure
        }
        exportStatusDetail = resultLines.joined(separator: "\n")

        isExporting = false
    }

    @MainActor
    private func makeExportContext() -> ExportContext? {
        let trimmedURL = serverURL.trimmingCharacters(in: .whitespacesAndNewlines)
        guard let url = URL(string: trimmedURL), let scheme = url.scheme, let host = url.host, !scheme.isEmpty, !host.isEmpty else {
            exportStatusTitle = "Failed"
            exportStatusDetail = "Enter a valid server URL such as http://100.x.x.x:7996."
            exportStatusTone = .failure
            return nil
        }

        return ExportContext(url: url, trimmedURL: trimmedURL)
    }
}

private struct IDECard<Content: View>: View {
    let title: String
    let subtitle: String
    let content: Content

    init(title: String, subtitle: String, @ViewBuilder content: () -> Content) {
        self.title = title
        self.subtitle = subtitle
        self.content = content()
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            VStack(alignment: .leading, spacing: 4) {
                Text(title)
                    .font(.system(size: 18, weight: .semibold))
                    .foregroundColor(.ideTextPrimary)

                Text(subtitle)
                    .font(.system(size: 13, weight: .medium))
                    .foregroundColor(.ideTextSecondary)
            }

            content
        }
        .padding(18)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(
            RoundedRectangle(cornerRadius: 22, style: .continuous)
                .fill(Color.idePanel.opacity(0.95))
                .overlay(
                    RoundedRectangle(cornerRadius: 22, style: .continuous)
                        .stroke(Color.ideBorder, lineWidth: 1)
                )
        )
    }
}

private struct DiagnosticRow: View {
    let label: String
    let value: String
    let tone: ExportStatusTone
    let accessibilityIdentifier: String?

    var body: some View {
        HStack(spacing: 12) {
            Text(label)
                .font(.system(size: 14, weight: .medium))
                .foregroundColor(.ideTextSecondary)

            Spacer(minLength: 12)

            Text(value)
                .font(.system(size: 13, weight: .semibold, design: .monospaced))
                .foregroundColor(tone == .neutral ? .ideTextPrimary : tone.color)
                .padding(.horizontal, 10)
                .padding(.vertical, 7)
                .background(
                    Capsule(style: .continuous)
                        .fill(tone.capsuleBackground)
                )
                .ifLet(accessibilityIdentifier) { view, id in
                    view.accessibilityIdentifier(id)
                }
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 14)
        .background(
            RoundedRectangle(cornerRadius: 16, style: .continuous)
                .fill(Color.idePanelElevated)
                .overlay(
                    RoundedRectangle(cornerRadius: 16, style: .continuous)
                        .stroke(Color.ideBorder, lineWidth: 1)
                )
        )
    }
}

private struct LogConsoleContent: View {
    let lines: [String]

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            ForEach(Array(lines.enumerated()), id: \.offset) { index, line in
                HStack(alignment: .top, spacing: 10) {
                    Text(String(format: "%03d", index + 1))
                        .font(.system(size: 11, weight: .medium, design: .monospaced))
                        .foregroundColor(.ideTextMuted)
                        .frame(width: 34, alignment: .trailing)

                    Text(line.isEmpty ? " " : line)
                        .font(.system(size: 12, weight: .medium, design: .monospaced))
                        .foregroundColor(.ideTextSecondary)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
                .id(index)
            }

            Color.clear
                .frame(height: 1)
                .id("bottom")
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(14)
    }
}

private struct ActionButton: View {
    let title: String
    let subtitle: String
    let icon: String
    let style: ActionButtonStyle
    let isPressed: Bool
    let isDisabled: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 14) {
                Image(systemName: icon)
                    .font(.system(size: 16, weight: .semibold))
                    .foregroundStyle(style.iconColor)
                    .frame(width: 18)

                VStack(alignment: .leading, spacing: 4) {
                    Text(title)
                        .font(.system(size: 16, weight: .semibold))
                        .foregroundStyle(style.titleColor)

                    Text(subtitle)
                        .font(.system(size: 13, weight: .medium))
                        .foregroundStyle(style.subtitleColor)
                        .multilineTextAlignment(.leading)
                }

                Spacer(minLength: 12)

                Image(systemName: "chevron.right")
                    .font(.system(size: 12, weight: .bold))
                    .foregroundStyle(style.chevronColor)
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 16)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(
                RoundedRectangle(cornerRadius: 18, style: .continuous)
                    .fill(style.background(isPressed: isPressed, isDisabled: isDisabled))
                    .overlay(
                        RoundedRectangle(cornerRadius: 18, style: .continuous)
                            .stroke(style.border(isPressed: isPressed, isDisabled: isDisabled), lineWidth: 1)
                    )
            )
        }
        .buttonStyle(.plain)
        .disabled(isDisabled)
        .opacity(isDisabled ? 0.72 : 1)
    }
}

private struct StatusPill: View {
    let label: String
    let tone: ExportStatusTone
    let icon: String

    var body: some View {
        HStack(spacing: 8) {
            Image(systemName: icon)
                .font(.system(size: 11, weight: .bold))

            Text(label)
                .font(.system(size: 11, weight: .bold, design: .monospaced))
        }
        .foregroundStyle(tone.color)
        .padding(.horizontal, 10)
        .padding(.vertical, 8)
        .background(
            Capsule(style: .continuous)
                .fill(tone.capsuleBackground)
        )
    }
}

private enum ExportStatusTone {
    case neutral
    case success
    case partial
    case failure

    var color: Color {
        switch self {
        case .neutral:
            return .ideInfo
        case .success:
            return .ideAccent
        case .partial:
            return .ideWarning
        case .failure:
            return .ideError
        }
    }

    var detailColor: Color {
        switch self {
        case .neutral:
            return .ideTextSecondary
        case .success:
            return .ideAccent
        case .partial:
            return .ideWarning
        case .failure:
            return .ideError
        }
    }

    var capsuleBackground: Color {
        switch self {
        case .neutral:
            return Color.ideInfo.opacity(0.14)
        case .success:
            return Color.ideAccent.opacity(0.14)
        case .partial:
            return Color.ideWarning.opacity(0.14)
        case .failure:
            return Color.ideError.opacity(0.14)
        }
    }

    var icon: String {
        switch self {
        case .neutral:
            return "bolt.horizontal.circle"
        case .success:
            return "checkmark.circle"
        case .partial:
            return "exclamationmark.triangle"
        case .failure:
            return "xmark.octagon"
        }
    }
}

private enum ActionButtonStyle {
    case primary
    case secondary

    func background(isPressed: Bool, isDisabled: Bool) -> Color {
        switch self {
        case .primary:
            if isDisabled { return Color.ideAccentMuted.opacity(0.72) }
            if isPressed { return Color.ideAccent.opacity(0.82) }
            return Color.ideAccent
        case .secondary:
            if isDisabled { return Color.idePanelElevated.opacity(0.72) }
            if isPressed { return Color.idePanelElevated.opacity(0.92) }
            return Color.idePanelElevated
        }
    }

    func border(isPressed: Bool, isDisabled: Bool) -> Color {
        switch self {
        case .primary:
            return Color.ideAccent.opacity(isDisabled ? 0.18 : 0.34)
        case .secondary:
            return isPressed ? Color.ideAccent.opacity(0.28) : Color.ideBorder
        }
    }

    var titleColor: Color {
        switch self {
        case .primary:
            return .black.opacity(0.88)
        case .secondary:
            return .ideTextPrimary
        }
    }

    var subtitleColor: Color {
        switch self {
        case .primary:
            return .black.opacity(0.64)
        case .secondary:
            return .ideTextSecondary
        }
    }

    var iconColor: Color {
        switch self {
        case .primary:
            return .black.opacity(0.88)
        case .secondary:
            return .ideAccent
        }
    }

    var chevronColor: Color {
        switch self {
        case .primary:
            return .black.opacity(0.65)
        case .secondary:
            return .ideTextMuted
        }
    }
}

private struct ExportContext {
    let url: URL
    let trimmedURL: String
}

private extension View {
    @ViewBuilder
    func ifLet<T, Content: View>(_ value: T?, transform: (Self, T) -> Content) -> some View {
        if let value {
            transform(self, value)
        } else {
            self
        }
    }
}
