import XCTest
@testable import HealthQuantificationIOS

final class ExportProfilerTests: XCTestCase {
    func testStrictProfileRoute() {
        let id = UUID()
        let url = URL(string: "healthquantification://profile-export?run_id=\(id.uuidString)")!
        let command = HealthExportDeepLinkParser.parse(url)
        XCTAssertEqual(command?.id, id)
        XCTAssertEqual(command?.profile, true)
        XCTAssertNil(HealthExportDeepLinkParser.parse(URL(string: url.absoluteString + "&run_id=bad")!))
        XCTAssertNil(HealthExportDeepLinkParser.parse(URL(string: url.absoluteString + "&server=http://example.com")!))
    }

    func testAtomicCompletionAndAggregatePrivacy() throws {
        let directory = FileManager.default.temporaryDirectory.appending(path: UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: directory) }
        let id = UUID()
        let profiler = ExportProfiler(runID: id, directory: directory)
        profiler.record("vitals.fetch", since: ExportProfiler.now(), count: 5)
        let result = HealthExportResult.aggregate([.success(.vitals, sent: 5, upserted: 5)])
        try profiler.finish(result)
        let data = try Data(contentsOf: directory.appending(path: "\(id.uuidString).json"))
        let decoder = JSONDecoder()
        let artifact = try decoder.decode(ExportProfileArtifact.self, from: data)
        XCTAssertEqual(artifact.runID, id.uuidString)
        XCTAssertEqual(artifact.status, "success")
        XCTAssertEqual(artifact.events.map(\.phase), ["vitals.fetch", "profiling.progress_overhead"])
        XCTAssertGreaterThanOrEqual(artifact.totalMs, 0)
        let object = try XCTUnwrap(JSONSerialization.jsonObject(with: data) as? [String: Any])
        XCTAssertEqual(Set(object.keys), Set(["schema_version", "run_id", "status", "total_ms", "events", "failed_categories", "build_configuration"]))
        profiler.add("late.metrics", milliseconds: 1)
        XCTAssertEqual(try Data(contentsOf: directory.appending(path: "\(id.uuidString).json")), data)
    }
}
