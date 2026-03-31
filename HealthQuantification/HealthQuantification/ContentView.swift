//
//  ContentView.swift
//  HealthQuantification
//
//  Created by Yan Wang on 3/30/26.
//

import SwiftUI

struct ContentView: View {
    @Bindable var model: HealthKitDiagnosticsModel

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Health Quantification")
                .font(.largeTitle)
            Text("Bundle-based HealthKit validation shell")
                .foregroundStyle(.secondary)

            HStack(spacing: 12) {
                Button("Run Doctor") {
                    model.runDoctor()
                }
                Button("Request Sleep Access") {
                    model.requestSleepAccess()
                }
            }

            GroupBox("Current Status") {
                VStack(alignment: .leading, spacing: 8) {
                    Text("healthDataAvailable: \(model.healthDataAvailableText)")
                    Text("authorization: \(model.authorizationState)")
                    Text("lastUpdated: \(model.lastUpdated)")
                }
                .frame(maxWidth: .infinity, alignment: .leading)
            }

            GroupBox("Log") {
                ScrollView {
                    Text(model.logText)
                        .font(.system(.body, design: .monospaced))
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .textSelection(.enabled)
                }
                .frame(width: 720, height: 260)
            }
        }
        .padding(24)
        .frame(width: 760, height: 520)
        .task {
            model.runDoctor()
        }
    }
}

#Preview {
    ContentView(model: HealthKitDiagnosticsModel())
}
