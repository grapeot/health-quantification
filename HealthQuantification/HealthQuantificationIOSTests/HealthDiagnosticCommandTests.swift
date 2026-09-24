import Foundation
import XCTest
@testable import HealthQuantificationIOS

final class HealthDiagnosticCommandTests: XCTestCase {
    private let id = "456EEB81-F801-4F0A-9C3F-9C9AFD9AB123"

    func testParsesOnlyBoundedReadOnlyDiagnostic() throws {
        let url = try XCTUnwrap(URL(string: "healthquantification://diagnostics?kind=physical-effort&run_id=\(id)&days=30"))
        let command = try XCTUnwrap(HealthDiagnosticDeepLinkParser.parse(url))
        XCTAssertEqual(command.runID.uuidString, id)
        XCTAssertEqual(command.days, 30)
        XCTAssertNil(HealthExportDeepLinkParser.parse(url))

        for invalid in [
            "healthquantification://diagnostics?kind=physical-effort&run_id=\(id)&days=31",
            "healthquantification://diagnostics?kind=physical-effort&run_id=\(id)&days=0",
            "healthquantification://diagnostics?kind=physical-effort&run_id=\(id)&days=30&server=https://example.test",
            "healthquantification://diagnostics?kind=physical-effort&run_id=\(id)&days=30&days=1",
            "healthquantification://diagnostics?kind=export-all&run_id=\(id)&days=30",
            "healthquantification://other@diagnostics?kind=physical-effort&run_id=\(id)&days=30",
            "healthquantification://diagnostics?kind=physical-effort&run_id=\(id)&days=30#fragment",
            "healthquantification://diagnostics?kind=physical-effort&run_id=../../bad&days=30",
        ] {
            XCTAssertNil(HealthDiagnosticDeepLinkParser.parse(try XCTUnwrap(URL(string: invalid))), invalid)
        }
    }

    func testWritesMinimalArtifactAtomically() throws {
        let root = FileManager.default.temporaryDirectory.appending(path: UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: root) }
        let artifact = HealthDiagnosticArtifact(
            schemaVersion: 1, runID: id, kind: "physical-effort", status: "completed",
            generatedAt: "2026-03-31T02:35:56Z", days: 30, sampleCount: 4,
            unit: "MET", minimum: 1.0, median: 3.0, p90: 5.0, maximum: 6.0,
            errorCode: nil
        )
        let url = try HealthDiagnosticArtifactStore.save(artifact, in: root)
        XCTAssertEqual(url.lastPathComponent, "\(id).json")
        let json = try XCTUnwrap(JSONSerialization.jsonObject(with: Data(contentsOf: url)) as? [String: Any])
        XCTAssertEqual(json["run_id"] as? String, id)
        XCTAssertEqual(json["sample_count"] as? Int, 4)
        XCTAssertEqual(json["unit"] as? String, "MET")
        XCTAssertNil(json["source_name"])
    }
}
