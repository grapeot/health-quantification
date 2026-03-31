//
//  HealthQuantificationApp.swift
//  HealthQuantification
//
//  Created by Yan Wang on 3/30/26.
//

import SwiftUI

@main
struct HealthQuantificationApp: App {
    @State private var model = HealthKitDiagnosticsModel()

    var body: some Scene {
        WindowGroup {
            ContentView(model: model)
        }
        .windowResizability(.contentSize)
    }
}
