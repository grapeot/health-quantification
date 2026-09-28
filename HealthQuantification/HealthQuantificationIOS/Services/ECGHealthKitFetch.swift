import Foundation
import HealthKit

extension HealthKitService {
    func fetchEcgSamples(days: Int) async throws -> [ECGRecord] {
        guard HKHealthStore.isHealthDataAvailable() || isUITestMockHealthDataAvailable else {
            throw HealthKitServiceError.healthDataUnavailable
        }
        if isUITestMockHealthDataAvailable {
            return []
        }

        let ecgType = HKObjectType.electrocardiogramType()
        try await requestReadAuthorization(readTypes: ecgReadTypes())
        let samples = try await queryElectrocardiograms(days: days, type: ecgType)
        var records: [ECGRecord] = []
        records.reserveCapacity(samples.count)
        for sample in samples {
            records.append(await makeECGRecord(from: sample))
        }
        let statusCounts = Dictionary(grouping: records, by: \.voltageStatus)
            .map { "\($0.key)=\($0.value.count)" }
            .sorted()
            .joined(separator: ",")
        appendLog(
            title: "fetchEcgSamples",
            payload: [
                "result": records.isEmpty ? "no_samples_returned" : "samples_returned",
                "count": String(records.count),
                "voltage_status_counts": statusCounts,
                "empty_result_does_not_prove_absence_or_normal": "true",
            ]
        )
        return records
    }

    func ecgReadTypes() -> Set<HKObjectType> {
        var readTypes: Set<HKObjectType> = [HKObjectType.electrocardiogramType()]
        for identifier in ECGExportMapping.symptomTypeIdentifiers {
            if let type = HKObjectType.categoryType(forIdentifier: identifier) {
                readTypes.insert(type)
            }
        }
        return readTypes
    }

    private func queryElectrocardiograms(days: Int, type: HKElectrocardiogramType) async throws -> [HKElectrocardiogram] {
        let now = Date()
        let startDate = Calendar.current.date(byAdding: .day, value: -days, to: now) ?? now
        let predicate = HKQuery.predicateForSamples(withStart: startDate, end: now, options: [])
        let sortDescriptors = [NSSortDescriptor(key: HKSampleSortIdentifierStartDate, ascending: true)]
        return try await withCheckedThrowingContinuation { continuation in
            let query = HKSampleQuery(
                sampleType: type,
                predicate: predicate,
                limit: HKObjectQueryNoLimit,
                sortDescriptors: sortDescriptors
            ) { _, samples, error in
                if let error {
                    continuation.resume(throwing: error)
                    return
                }
                continuation.resume(returning: (samples as? [HKElectrocardiogram]) ?? [])
            }
            healthStore.execute(query)
        }
    }

    private func makeECGRecord(from sample: HKElectrocardiogram) async -> ECGRecord {
        var voltages: [Double?] = []
        var points: [ECGVoltagePoint] = []
        var queryFailed = false
        let descriptor = HKElectrocardiogramQueryDescriptor(sample)
        do {
            for try await measurement in descriptor.results(for: healthStore) {
                let volts = volts(from: measurement)
                voltages.append(volts)
                points.append(
                    ECGVoltagePoint(
                        timeOffsetSeconds: measurement.timeSinceSampleStart,
                        voltageVolts: volts
                    )
                )
            }
        } catch {
            queryFailed = true
        }
        let assessment = ECGExportMapping.voltageAssessment(
            expectedCount: sample.numberOfVoltageMeasurements,
            voltages: voltages,
            queryFailed: queryFailed
        )
        let symptoms = await associatedSymptoms(for: sample)
        let heartRateUnit = HKUnit.count().unitDivided(by: .minute())
        let hertz = HKUnit.hertz()
        var metadata: [String: String] = [:]
        var algorithmVersion: Int?
        if let version = sample.metadata?[HKMetadataKeyAppleECGAlgorithmVersion] as? NSNumber {
            algorithmVersion = version.intValue
            metadata["apple_ecg_algorithm_version"] = version.stringValue
        }
        return ECGRecord(
            sourceID: sample.uuid.uuidString,
            startAt: Self.isoTimestamp(sample.startDate),
            endAt: Self.isoTimestamp(sample.endDate),
            algorithmClassification: ECGExportMapping.classificationName(rawValue: sample.classification.rawValue),
            algorithmClassificationValue: sample.classification.rawValue,
            symptomsStatus: ECGExportMapping.symptomsStatusName(rawValue: sample.symptomsStatus.rawValue),
            symptomsStatusValue: sample.symptomsStatus.rawValue,
            averageHeartRateBPM: compatibleValue(sample.averageHeartRate, unit: heartRateUnit),
            samplingFrequencyHz: compatibleValue(sample.samplingFrequency, unit: hertz),
            numberOfVoltageMeasurements: sample.numberOfVoltageMeasurements,
            voltageCount: points.count,
            voltageUnit: points.isEmpty ? nil : ECGExportMapping.voltageUnit,
            lead: ECGExportMapping.leadName,
            voltageStatus: assessment.status,
            voltageErrorCode: assessment.errorCode,
            algorithmVersion: algorithmVersion,
            sourceBundleID: sample.sourceRevision.source.bundleIdentifier,
            sourceName: sample.sourceRevision.source.name,
            symptoms: symptoms.records,
            symptomsReadStatus: symptoms.status,
            metadata: metadata,
            voltage: points
        )
    }

    private func associatedSymptoms(
        for sample: HKElectrocardiogram
    ) async -> (records: [ECGSymptomRecord], status: String) {
        let symptomsStatus = ECGExportMapping.symptomsStatusName(rawValue: sample.symptomsStatus.rawValue)
        guard symptomsStatus == "present" else {
            return ([], ECGExportMapping.symptomsReadStatus(
                symptomsStatus: symptomsStatus,
                queried: 0,
                failed: 0,
                returned: 0
            ))
        }
        let predicate = HKQuery.predicateForObjectsAssociated(electrocardiogram: sample)
        var records: [ECGSymptomRecord] = []
        var queried = 0
        var failed = 0
        for identifier in ECGExportMapping.symptomTypeIdentifiers {
            guard let type = HKObjectType.categoryType(forIdentifier: identifier) else {
                continue
            }
            queried += 1
            do {
                let samples = try await queryCategorySamples(type: type, predicate: predicate)
                records.append(contentsOf: samples.map { symptomRecord(from: $0, identifier: identifier) })
            } catch {
                failed += 1
            }
        }
        return (
            records,
            ECGExportMapping.symptomsReadStatus(
                symptomsStatus: symptomsStatus,
                queried: queried,
                failed: failed,
                returned: records.count
            )
        )
    }

    private func queryCategorySamples(
        type: HKCategoryType,
        predicate: NSPredicate
    ) async throws -> [HKCategorySample] {
        try await withCheckedThrowingContinuation { continuation in
            let query = HKSampleQuery(
                sampleType: type,
                predicate: predicate,
                limit: HKObjectQueryNoLimit,
                sortDescriptors: nil
            ) { _, samples, error in
                if let error {
                    continuation.resume(throwing: error)
                    return
                }
                continuation.resume(returning: (samples as? [HKCategorySample]) ?? [])
            }
            healthStore.execute(query)
        }
    }

    private func symptomRecord(
        from sample: HKCategorySample,
        identifier: HKCategoryTypeIdentifier
    ) -> ECGSymptomRecord {
        ECGSymptomRecord(
            symptomType: ECGExportMapping.symptomTypeName(identifier),
            severity: ECGExportMapping.severityName(rawValue: sample.value),
            severityValue: sample.value,
            sourceID: sample.uuid.uuidString
        )
    }

    private func volts(from measurement: HKElectrocardiogram.VoltageMeasurement) -> Double? {
        guard let quantity = measurement.quantity(for: .appleWatchSimilarToLeadI) else {
            return nil
        }
        let unit = HKUnit.volt()
        guard quantity.is(compatibleWith: unit) else {
            return nil
        }
        return quantity.doubleValue(for: unit)
    }

    private func compatibleValue(_ quantity: HKQuantity?, unit: HKUnit) -> Double? {
        guard let quantity, quantity.is(compatibleWith: unit) else {
            return nil
        }
        return quantity.doubleValue(for: unit)
    }
}
