import Foundation
import XCTest
@testable import HealthQuantificationIOS

final class HealthExportCommandTests: XCTestCase {
    private let callbackID = "inv_abcdefghijklmnopqrstuvwxyz0123456789ABCDEFG"

    func testParsesLegacyExportWithoutCallback() throws {
        let url = try XCTUnwrap(URL(string: "healthquantification://export-all"))
        let command = try XCTUnwrap(HealthExportDeepLinkParser.parse(url))
        XCTAssertNil(command.callback)
    }

    func testParsesStrictOpenCodeCallback() throws {
        let callback = "opencode://client-action-return/\(callbackID)"
        var components = URLComponents(string: "healthquantification://export-all")
        components?.queryItems = [URLQueryItem(name: "callback", value: callback)]

        let command = try XCTUnwrap(HealthExportDeepLinkParser.parse(try XCTUnwrap(components?.url)))

        XCTAssertEqual(command.callback?.callbackID, callbackID)
        XCTAssertEqual(command.callback?.url.absoluteString, callback)
    }

    func testRejectsUntrustedOrMalformedCallbacks() throws {
        let callbacks = [
            "https://example.com/client-action-return/\(callbackID)",
            "otherapp://client-action-return/\(callbackID)",
            "opencode://session/\(callbackID)",
            "opencode://client-action-return/short",
            "opencode://client-action-return/\(callbackID)/extra",
            "opencode://client-action-return/%5F\(callbackID)",
            "opencode://user@client-action-return/\(callbackID)",
            "opencode://client-action-return:4096/\(callbackID)",
            "opencode://client-action-return/\(callbackID)#fragment",
            "opencode://client-action-return/\(callbackID)?status=success",
            "opencode://client-action-ret%75rn/\(callbackID)",
        ]

        for callback in callbacks {
            var components = URLComponents(string: "healthquantification://export-all")
            components?.queryItems = [URLQueryItem(name: "callback", value: callback)]
            let url = try XCTUnwrap(components?.url)
            XCTAssertNil(HealthExportDeepLinkParser.parse(url), "Expected callback to be rejected: \(callback)")
        }
    }

    func testRejectsUnknownOuterQueryItems() throws {
        let url = try XCTUnwrap(URL(string: "healthquantification://export-all?server_url=https://attacker.example"))
        XCTAssertNil(HealthExportDeepLinkParser.parse(url))

        for value in ["?callback", "?callback="] {
            let missingCallback = try XCTUnwrap(URL(string: "healthquantification://export-all\(value)"))
            XCTAssertNil(HealthExportDeepLinkParser.parse(missingCallback))
        }
    }

    @MainActor
    func testRuntimeSuppressesDuplicateScenesAndConcurrentCommands() {
        var runtime = HealthExportRuntime()
        let firstID = UUID()
        let secondID = UUID()

        guard case let .start(executionID) = runtime.begin(commandID: firstID) else {
            return XCTFail("Expected the first command to start")
        }
        XCTAssertTrue(runtime.isExporting)
        XCTAssertEqual(runtime.begin(commandID: firstID), .duplicate)
        XCTAssertEqual(runtime.begin(commandID: secondID), .busy)
        XCTAssertEqual(runtime.begin(commandID: secondID), .duplicate)

        runtime.finish(executionID: executionID)
        XCTAssertFalse(runtime.isExporting)
    }

    func testServerURLAcceptsOnlyHTTPWithoutCredentialsOrFragment() {
        XCTAssertNotNil(HealthExportServerURLParser.parse(" http://localhost:7996 "))
        XCTAssertNotNil(HealthExportServerURLParser.parse("https://health.example.test/ingest"))
        XCTAssertNil(HealthExportServerURLParser.parse("file://localhost/tmp"))
        XCTAssertNil(HealthExportServerURLParser.parse("ftp://health.example.test"))
        XCTAssertNil(HealthExportServerURLParser.parse("http://user:pass@health.example.test"))
        XCTAssertNil(HealthExportServerURLParser.parse("http://health.example.test#fragment"))
    }

    func testBuildsBoundedSuccessAndPartialCallbacks() throws {
        let callback = HealthExportCallback(
            url: try XCTUnwrap(URL(string: "opencode://client-action-return/\(callbackID)")),
            callbackID: callbackID
        )
        let success = HealthExportResult(
            status: .success,
            sent: 12,
            upserted: 11,
            failedCategories: [],
            errorCode: nil,
            categoryResults: []
        )
        let successURL = try XCTUnwrap(HealthExportCallbackBuilder.url(for: callback, result: success))
        let successItems = try XCTUnwrap(URLComponents(url: successURL, resolvingAgainstBaseURL: false)?.queryItems)
        XCTAssertEqual(Dictionary(uniqueKeysWithValues: successItems.map { ($0.name, $0.value ?? "") }), [
            "status": "success",
            "sent": "12",
            "upserted": "11",
        ])

        let partial = HealthExportResult(
            status: .partial,
            sent: 8,
            upserted: 8,
            failedCategories: [.sleep, .workouts],
            errorCode: .categoryFailure,
            categoryResults: []
        )
        let partialURL = try XCTUnwrap(HealthExportCallbackBuilder.url(for: callback, result: partial))
        let partialItems = try XCTUnwrap(URLComponents(url: partialURL, resolvingAgainstBaseURL: false)?.queryItems)
        XCTAssertEqual(Dictionary(uniqueKeysWithValues: partialItems.map { ($0.name, $0.value ?? "") }), [
            "status": "partial",
            "sent": "8",
            "upserted": "8",
            "failed": "sleep,workouts",
            "error_code": "category_failure",
        ])

        let failedURL = try XCTUnwrap(HealthExportCallbackBuilder.url(
            for: callback,
            result: .failed(.invalidServerURL)
        ))
        let failedItems = try XCTUnwrap(URLComponents(url: failedURL, resolvingAgainstBaseURL: false)?.queryItems)
        XCTAssertEqual(Dictionary(uniqueKeysWithValues: failedItems.map { ($0.name, $0.value ?? "") }), [
            "status": "failed",
            "sent": "0",
            "upserted": "0",
            "error_code": "invalid_server_url",
        ])

        let busyURL = try XCTUnwrap(HealthExportCallbackBuilder.url(for: callback, result: .busy))
        let busyItems = try XCTUnwrap(URLComponents(url: busyURL, resolvingAgainstBaseURL: false)?.queryItems)
        XCTAssertEqual(Dictionary(uniqueKeysWithValues: busyItems.map { ($0.name, $0.value ?? "") }), [
            "status": "busy",
            "sent": "0",
            "upserted": "0",
            "error_code": "export_in_progress",
        ])
    }

    func testAggregatesSuccessPartialAndFailure() {
        let success = HealthExportResult.aggregate([
            .success(.sleep, sent: 4, upserted: 4),
            .success(.body, sent: 0, upserted: 0),
        ])
        XCTAssertEqual(success.status, .success)
        XCTAssertEqual(success.sent, 4)

        let partial = HealthExportResult.aggregate([
            .success(.sleep, sent: 4, upserted: 4),
            .failure(.workouts, error: TestError.expected),
        ])
        XCTAssertEqual(partial.status, .partial)
        XCTAssertEqual(partial.failedCategories, [.workouts])
        XCTAssertEqual(partial.errorCode, .categoryFailure)

        let failed = HealthExportResult.aggregate([
            .failure(.sleep, error: TestError.expected),
            .failure(.workouts, error: TestError.expected),
        ])
        XCTAssertEqual(failed.status, .failed)
    }
}

private enum TestError: LocalizedError {
    case expected

    var errorDescription: String? { "expected failure" }
}
