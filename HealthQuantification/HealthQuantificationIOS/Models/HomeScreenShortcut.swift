import UIKit

enum HomeScreenShortcut {
    static let exportAllType = "healthquantification.export-all"
}

enum HomeScreenShortcutParser {
    static func command(from item: UIApplicationShortcutItem) -> HealthExportCommand? {
        guard item.type == HomeScreenShortcut.exportAllType else { return nil }
        return HealthExportCommand(callback: nil)
    }
}

@MainActor
final class HomeScreenExportRouter {
    static let shared = HomeScreenExportRouter()

    private var pending: [HealthExportCommand] = []
    private var handler: ((HealthExportCommand) -> Void)?

    @discardableResult
    func accept(_ item: UIApplicationShortcutItem) -> Bool {
        guard let command = HomeScreenShortcutParser.command(from: item) else { return false }
        deliver(command)
        return true
    }

    func deliver(_ command: HealthExportCommand) {
        if let handler {
            handler(command)
        } else {
            pending.append(command)
        }
    }

    func attach(_ handler: @escaping (HealthExportCommand) -> Void) {
        self.handler = handler
        let queued = pending
        pending.removeAll()
        queued.forEach(handler)
    }

    var hasHandler: Bool { handler != nil }
    var pendingCount: Int { pending.count }
}
