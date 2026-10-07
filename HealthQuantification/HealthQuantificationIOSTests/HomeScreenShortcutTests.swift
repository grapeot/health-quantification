import UIKit
import XCTest
@testable import HealthQuantificationIOS

final class HomeScreenShortcutTests: XCTestCase {
    @MainActor
    func testKnownShortcutMatchesNoCallbackExport() throws {
        let item = shortcutItem(userInfo: ["server_url": "http://127.0.0.1:9" as NSString])
        let command = try XCTUnwrap(HomeScreenShortcutParser.command(from: item))
        let deepLink = try XCTUnwrap(
            HealthExportDeepLinkParser.parse(XCTUnwrap(URL(string: "healthquantification://export-all")))
        )

        XCTAssertNil(command.callback)
        XCTAssertFalse(command.profile)
        XCTAssertNil(deepLink.callback)
        XCTAssertEqual(command.profile, deepLink.profile)
    }

    @MainActor
    func testRejectsUnknownTypesAndDoesNotQueueThem() {
        let router = HomeScreenExportRouter()
        let rejected = [
            "healthquantification://export-all",
            "https://127.0.0.1/export-all",
            "export-all",
            "",
        ]

        for type in rejected {
            let item = UIApplicationShortcutItem(type: type, localizedTitle: "Transfer Now")
            XCTAssertNil(HomeScreenShortcutParser.command(from: item), type)
            XCTAssertFalse(router.accept(item), type)
        }
        XCTAssertEqual(router.pendingCount, 0)
    }

    @MainActor
    func testSharedSessionBlocksASecondExport() {
        let session = HealthAppSession.shared
        let first = UUID()
        let start = session.exportRuntime.begin(commandID: first)
        defer { session.exportRuntime.finish(executionID: first) }
        XCTAssertEqual(start, .start(executionID: first))
        XCTAssertTrue(session === HealthAppSession.shared)
        XCTAssertEqual(HealthAppSession.shared.exportRuntime.begin(commandID: UUID()), .busy)
    }

    @MainActor
    func testColdQueueIsNotLostAndConcurrentShortcutDoesNotStartTwice() {
        let router = HomeScreenExportRouter()
        let item = shortcutItem(userInfo: ["callback": "https://127.0.0.1/return" as NSString])
        XCTAssertTrue(router.accept(item))
        XCTAssertTrue(router.accept(item))
        XCTAssertFalse(router.hasHandler)
        XCTAssertEqual(router.pendingCount, 2)

        var runtime = HealthExportRuntime()
        var started: [UUID] = []
        router.attach { command in
            XCTAssertNil(command.callback)
            XCTAssertFalse(command.profile)
            switch runtime.begin(commandID: command.id) {
            case let .start(id):
                started.append(id)
            case .busy, .duplicate:
                break
            }
        }

        XCTAssertEqual(started.count, 1)
        XCTAssertEqual(router.pendingCount, 0)
        XCTAssertTrue(router.hasHandler)

        XCTAssertTrue(router.accept(item))
        XCTAssertEqual(started.count, 1)

        runtime.finish(executionID: started[0])
        XCTAssertTrue(router.accept(item))
        XCTAssertEqual(started.count, 2)
    }

    func testBundleDeclaresOnlyTheStaticExportShortcut() throws {
        let bundle = Bundle(for: HealthKitService.self)
        let plistURL = try XCTUnwrap(bundle.url(forResource: "Info", withExtension: "plist"))
        let plist = try XCTUnwrap(NSDictionary(contentsOf: plistURL))
        let items = try XCTUnwrap(plist["UIApplicationShortcutItems"] as? [[String: Any]])

        XCTAssertEqual(items.count, 1)
        XCTAssertEqual(items[0]["UIApplicationShortcutItemType"] as? String, HomeScreenShortcut.exportAllType)
        let title = items[0]["UIApplicationShortcutItemTitle"] as? String
        let subtitle = items[0]["UIApplicationShortcutItemSubtitle"] as? String
        XCTAssertEqual(title, "Transfer Now")
        XCTAssertFalse(title?.contains("http") ?? true)
        XCTAssertFalse(subtitle?.contains("http") ?? false)
        XCTAssertFalse(subtitle?.contains("://") ?? false)
        XCTAssertNil(items[0]["UIApplicationShortcutItemUserInfo"])
        XCTAssertNil(items[0]["UIApplicationShortcutItemTargetURL"])
    }

    private func shortcutItem(userInfo: [String: NSSecureCoding]) -> UIApplicationShortcutItem {
        UIApplicationShortcutItem(
            type: HomeScreenShortcut.exportAllType,
            localizedTitle: "Transfer Now",
            localizedSubtitle: nil,
            icon: nil,
            userInfo: userInfo
        )
    }
}
