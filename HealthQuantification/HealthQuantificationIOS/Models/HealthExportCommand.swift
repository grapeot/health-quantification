import Foundation

enum HealthExportCategory: String, CaseIterable, Codable, Equatable {
    case sleep
    case vitals
    case body
    case lifestyle
    case activity
    case workouts
}

enum HealthExportStatus: String, Codable, Equatable {
    case success
    case partial
    case failed
    case busy
}

enum HealthExportErrorCode: String, Codable, Equatable {
    case categoryFailure = "category_failure"
    case exportInProgress = "export_in_progress"
    case invalidServerURL = "invalid_server_url"
}

struct HealthExportCallback: Equatable {
    let url: URL
    let callbackID: String
}

struct HealthExportCommand: Equatable, Identifiable {
    let id: UUID
    let callback: HealthExportCallback?

    init(id: UUID = UUID(), callback: HealthExportCallback?) {
        self.id = id
        self.callback = callback
    }
}

enum HealthExportStartDecision: Equatable {
    case start(executionID: UUID)
    case busy
    case duplicate
}

struct HealthExportRuntime {
    private(set) var isExporting = false
    private var activeExecutionID: UUID?
    private var observedCommandIDs: [UUID] = []

    mutating func begin(commandID: UUID?) -> HealthExportStartDecision {
        if let commandID {
            guard !observedCommandIDs.contains(commandID) else { return .duplicate }
            observedCommandIDs.append(commandID)
            if observedCommandIDs.count > 50 {
                observedCommandIDs.removeFirst(observedCommandIDs.count - 50)
            }
        }

        guard activeExecutionID == nil else { return .busy }
        let executionID = commandID ?? UUID()
        activeExecutionID = executionID
        isExporting = true
        return .start(executionID: executionID)
    }

    mutating func finish(executionID: UUID) {
        guard activeExecutionID == executionID else { return }
        activeExecutionID = nil
        isExporting = false
    }
}

struct HealthExportCategoryResult: Equatable {
    let category: HealthExportCategory
    let sent: Int
    let upserted: Int
    let errorDescription: String?

    static func success(_ category: HealthExportCategory, sent: Int, upserted: Int) -> Self {
        Self(category: category, sent: sent, upserted: upserted, errorDescription: nil)
    }

    static func failure(_ category: HealthExportCategory, error: Error) -> Self {
        Self(category: category, sent: 0, upserted: 0, errorDescription: error.localizedDescription)
    }

    var line: String {
        if let errorDescription {
            return "[\(category.rawValue)] failed: \(errorDescription)"
        }
        if sent == 0 {
            return "[\(category.rawValue)] no data"
        }
        return "[\(category.rawValue)] sent \(sent), upserted \(upserted)"
    }
}

struct HealthExportResult: Equatable {
    let status: HealthExportStatus
    let sent: Int
    let upserted: Int
    let failedCategories: [HealthExportCategory]
    let errorCode: HealthExportErrorCode?
    let categoryResults: [HealthExportCategoryResult]

    static func aggregate(_ results: [HealthExportCategoryResult]) -> Self {
        let failures = results.filter { $0.errorDescription != nil }.map(\.category)
        let successCount = results.count - failures.count
        let status: HealthExportStatus = if failures.isEmpty {
            .success
        } else if successCount > 0 {
            .partial
        } else {
            .failed
        }
        return Self(
            status: status,
            sent: results.reduce(0) { $0 + $1.sent },
            upserted: results.reduce(0) { $0 + $1.upserted },
            failedCategories: failures,
            errorCode: failures.isEmpty ? nil : .categoryFailure,
            categoryResults: results
        )
    }

    static func failed(_ code: HealthExportErrorCode) -> Self {
        Self(status: .failed, sent: 0, upserted: 0, failedCategories: [], errorCode: code, categoryResults: [])
    }

    static let busy = Self(
        status: .busy,
        sent: 0,
        upserted: 0,
        failedCategories: [],
        errorCode: .exportInProgress,
        categoryResults: []
    )

    var callbackQueryItems: [URLQueryItem] {
        var items = [
            URLQueryItem(name: "status", value: status.rawValue),
            URLQueryItem(name: "sent", value: String(sent)),
            URLQueryItem(name: "upserted", value: String(upserted)),
        ]
        if !failedCategories.isEmpty {
            items.append(URLQueryItem(name: "failed", value: failedCategories.map(\.rawValue).joined(separator: ",")))
        }
        if let errorCode {
            items.append(URLQueryItem(name: "error_code", value: errorCode.rawValue))
        }
        return items
    }
}

enum HealthExportDeepLinkParser {
    static func parse(_ url: URL) -> HealthExportCommand? {
        guard url.scheme?.lowercased() == "healthquantification",
              url.user == nil,
              url.password == nil,
              url.port == nil,
              url.fragment == nil else {
            return nil
        }

        let normalizedAction = [url.host, url.path]
            .compactMap { $0 }
            .joined(separator: "/")
            .trimmingCharacters(in: CharacterSet(charactersIn: "/"))
            .lowercased()
        guard normalizedAction == "export-all" || normalizedAction == "export/all" else {
            return nil
        }

        guard let components = URLComponents(url: url, resolvingAgainstBaseURL: false) else {
            return nil
        }
        let queryItems = components.queryItems ?? []
        guard queryItems.allSatisfy({ $0.name == "callback" }), queryItems.count <= 1 else {
            return nil
        }
        guard let callbackItem = queryItems.first else {
            return HealthExportCommand(callback: nil)
        }
        guard let rawCallback = callbackItem.value,
              !rawCallback.isEmpty,
              rawCallback.count <= 512,
              let callbackURL = URL(string: rawCallback),
              let callback = parseCallback(callbackURL) else {
            return nil
        }
        return HealthExportCommand(callback: callback)
    }

    private static func parseCallback(_ url: URL) -> HealthExportCallback? {
        guard let components = URLComponents(url: url, resolvingAgainstBaseURL: false),
              components.scheme?.lowercased() == "opencode",
              components.host?.lowercased() == "client-action-return",
              components.percentEncodedHost?.lowercased() == "client-action-return",
              components.user == nil,
              components.password == nil,
              components.port == nil,
              components.query == nil,
              components.fragment == nil else {
            return nil
        }
        let encodedPath = components.percentEncodedPath
        guard encodedPath.hasPrefix("/"), encodedPath.count > 1 else { return nil }
        let encodedID = String(encodedPath.dropFirst())
        guard !encodedID.contains("/"),
              let callbackID = encodedID.removingPercentEncoding,
              encodedID == callbackID,
              isValidCallbackID(callbackID) else {
            return nil
        }
        return HealthExportCallback(url: url, callbackID: callbackID)
    }

    private static func isValidCallbackID(_ value: String) -> Bool {
        guard (43...128).contains(value.count) else { return false }
        return value.unicodeScalars.allSatisfy { scalar in
            switch scalar.value {
            case 45, 48...57, 65...90, 95, 97...122:
                return true
            default:
                return false
            }
        }
    }
}

enum HealthExportServerURLParser {
    static func parse(_ value: String) -> URL? {
        let trimmed = value.trimmingCharacters(in: .whitespacesAndNewlines)
        guard let components = URLComponents(string: trimmed),
              let scheme = components.scheme?.lowercased(),
              scheme == "http" || scheme == "https",
              components.host?.isEmpty == false,
              components.user == nil,
              components.password == nil,
              components.fragment == nil else {
            return nil
        }
        return components.url
    }
}

enum HealthExportCallbackBuilder {
    static func url(for callback: HealthExportCallback, result: HealthExportResult) -> URL? {
        guard var components = URLComponents(url: callback.url, resolvingAgainstBaseURL: false) else {
            return nil
        }
        components.queryItems = result.callbackQueryItems
        return components.url
    }
}
