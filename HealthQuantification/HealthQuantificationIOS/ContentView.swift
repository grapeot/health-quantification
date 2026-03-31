//
//  ContentView.swift
//  HealthQuantificationIOS
//
//  Created by Yan Wang on 3/30/26.
//

import SwiftUI

struct ContentView: View {
    @Bindable var model: HealthKitService
    @Binding var serverURL: String

    @State private var isExporting = false
    @State private var exportStatusTitle = "No export yet"
    @State private var exportStatusDetail = "Enter a server URL, request access if needed, then export 30 days of HealthKit data."
    @State private var exportStatusTone: ExportStatusTone = .neutral

    private let ingestClient = IngestClient()

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                Text("Health Quantification iOS")
                    .font(.largeTitle)
                    .fontWeight(.semibold)

                Text("Minimal HealthKit validation client")
                    .foregroundStyle(.secondary)

                HStack(spacing: 12) {
                    Button("Run Doctor") {
                        model.runDoctor()
                    }
                    .buttonStyle(.borderedProminent)
                    .accessibilityIdentifier("runDoctorButton")

                    Button("Request Health Access") {
                        model.requestHealthAccess()
                    }
                    .buttonStyle(.bordered)
                    .accessibilityIdentifier("requestSleepAccessButton")
                }

                VStack(alignment: .leading, spacing: 8) {
                    Text("Server URL")
                        .font(.headline)

                    TextField("http://localhost:7996", text: $serverURL)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                        .keyboardType(.URL)
                        .textFieldStyle(.roundedBorder)
                        .accessibilityIdentifier("serverURLField")

                    HStack(spacing: 12) {
                        Button(isExporting ? "Exporting..." : "Export Sleep (30 days)") {
                            Task {
                                await exportSleep()
                            }
                        }
                        .buttonStyle(.borderedProminent)
                        .disabled(isExporting)
                        .accessibilityIdentifier("exportSleepButton")

                        Button(isExporting ? "Exporting..." : "Export All (30 days)") {
                            Task {
                                await exportAll()
                            }
                        }
                        .buttonStyle(.bordered)
                        .disabled(isExporting)
                        .accessibilityIdentifier("exportAllButton")
                    }
                }

                VStack(alignment: .leading, spacing: 8) {
                    Text("Exports: sleep → /ingest/sleep, vitals → /ingest/vitals, body → /ingest/body, lifestyle → /ingest/lifestyle, activity → /ingest/activity")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }

                VStack(alignment: .leading, spacing: 8) {
                    Text(exportStatusTitle)
                        .font(.headline)
                        .foregroundStyle(exportStatusTone.color)
                        .accessibilityIdentifier("exportStatusTitle")

                    Text(exportStatusDetail)
                        .font(.system(.body, design: .monospaced))
                        .accessibilityIdentifier("exportStatusDetail")
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding()
                .background(exportStatusTone.backgroundColor)
                .clipShape(RoundedRectangle(cornerRadius: 12))

                VStack(alignment: .leading, spacing: 8) {
                    Text("healthDataAvailable: \(model.healthDataAvailableText)")
                        .accessibilityIdentifier("healthDataAvailableLabel")
                    Text("authorization: \(model.authorizationState)")
                        .accessibilityIdentifier("authorizationStateLabel")
                    Text("lastUpdated: \(model.lastUpdated)")
                }
                .font(.system(.body, design: .monospaced))
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding()
                .background(Color(uiColor: .secondarySystemBackground))
                .clipShape(RoundedRectangle(cornerRadius: 12))

                Text(model.logText)
                    .font(.system(.body, design: .monospaced))
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding()
                    .background(Color(uiColor: .secondarySystemBackground))
                    .clipShape(RoundedRectangle(cornerRadius: 12))
                    .textSelection(.enabled)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding()
        }
        .task {
            model.runDoctor()
        }
    }

    @MainActor
    private func exportSleep() async {
        guard let exportContext = makeExportContext() else {
            return
        }

        isExporting = true
        exportStatusTitle = "Exporting sleep data"
        exportStatusDetail = "Fetching the last 30 days from HealthKit and sending sleep samples to \(exportContext.trimmedURL)."
        exportStatusTone = .neutral

        do {
            let samples = try await model.fetchSleepSamples(days: 30)
            let response = try await ingestClient.ingestSleep(serverURL: exportContext.url, samples: samples)
            exportStatusTitle = "Export succeeded"
            exportStatusDetail = "Sent \(samples.count) samples. Server status: \(response.status), upserted: \(response.upserted), total_samples: \(response.totalSamples)."
            exportStatusTone = .success
        } catch {
            exportStatusTitle = "Export failed"
            exportStatusDetail = error.localizedDescription
            exportStatusTone = .failure
        }

        isExporting = false
    }

    @MainActor
    private func exportAll() async {
        guard let exportContext = makeExportContext() else {
            return
        }

        isExporting = true
        exportStatusTitle = "Exporting all HealthKit data"
        exportStatusDetail = "Fetching sleep, vitals, body, lifestyle, and activity samples from the last 30 days and sending them to \(exportContext.trimmedURL)."
        exportStatusTone = .neutral

        do {
            let sleepSamples = try await model.fetchSleepSamples(days: 30)
            let vitalsSamples = try await model.fetchVitalsSamples(days: 30)
            let bodySamples = try await model.fetchBodySamples(days: 30)
            let lifestyleSamples = try await model.fetchLifestyleSamples(days: 30)
            let activitySamples = try await model.fetchActivitySamples(days: 30)

            let sleepResponse = try await ingestClient.ingestSleep(serverURL: exportContext.url, samples: sleepSamples)
            let vitalsResponse = try await ingestClient.ingestVitals(serverURL: exportContext.url, samples: vitalsSamples)
            let bodyResponse = try await ingestClient.ingestBody(serverURL: exportContext.url, samples: bodySamples)
            let lifestyleResponse = try await ingestClient.ingestLifestyle(serverURL: exportContext.url, samples: lifestyleSamples)
            let activityResponse = try await ingestClient.ingestActivity(serverURL: exportContext.url, samples: activitySamples)

            exportStatusTitle = "Export succeeded"
            exportStatusDetail = [
                "sleep: sent \(sleepSamples.count), upserted \(sleepResponse.upserted)",
                "vitals: sent \(vitalsSamples.count), upserted \(vitalsResponse.upserted)",
                "body: sent \(bodySamples.count), upserted \(bodyResponse.upserted)",
                "lifestyle: sent \(lifestyleSamples.count), upserted \(lifestyleResponse.upserted)",
                "activity: sent \(activitySamples.count), upserted \(activityResponse.upserted)",
            ].joined(separator: "\n")
            exportStatusTone = .success
        } catch {
            exportStatusTitle = "Export failed"
            exportStatusDetail = error.localizedDescription
            exportStatusTone = .failure
        }

        isExporting = false
    }

    @MainActor
    private func makeExportContext() -> ExportContext? {
        let trimmedURL = serverURL.trimmingCharacters(in: .whitespacesAndNewlines)
        guard let url = URL(string: trimmedURL), let scheme = url.scheme, let host = url.host, !scheme.isEmpty, !host.isEmpty else {
            exportStatusTitle = "Export failed"
            exportStatusDetail = "Enter a valid server URL such as http://100.x.x.x:7996."
            exportStatusTone = .failure
            return nil
        }

        return ExportContext(url: url, trimmedURL: trimmedURL)
    }
}

#Preview {
    ContentView(model: HealthKitService(), serverURL: .constant("http://localhost:7996"))
}

private enum ExportStatusTone {
    case neutral
    case success
    case failure

    var color: Color {
        switch self {
        case .neutral:
            return .primary
        case .success:
            return .green
        case .failure:
            return .red
        }
    }

    var backgroundColor: Color {
        switch self {
        case .neutral:
            return Color(uiColor: .secondarySystemBackground)
        case .success:
            return Color.green.opacity(0.12)
        case .failure:
            return Color.red.opacity(0.12)
        }
    }
}

private struct ExportContext {
    let url: URL
    let trimmedURL: String
}
