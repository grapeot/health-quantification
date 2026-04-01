import Foundation
import HealthKit
import Observation

@MainActor
@Observable
final class HealthKitService {
    var healthDataAvailableText = "unknown"
    var authorizationState = "not_requested"
    var lastUpdated = "never"
    var logEntries: [String] = []

    private let healthStore = HKHealthStore()
    private let processInfo: ProcessInfo

    init(processInfo: ProcessInfo = .processInfo) {
        self.processInfo = processInfo
    }

    var logText: String {
        if logEntries.isEmpty {
            return "No events yet. Tap Run Doctor, Request Health Access, or Export All."
        }
        return logEntries.joined(separator: "\n\n")
    }

    func runDoctor() {
        let available = isUITestMockHealthDataAvailable ? true : HKHealthStore.isHealthDataAvailable()
        healthDataAvailableText = available ? "true" : "false"
        lastUpdated = Self.isoTimestamp(Date())
        appendLog(
            title: "doctor",
            payload: [
                "platform": "iOS",
                "healthDataAvailable": healthDataAvailableText,
                "timestamp": lastUpdated,
            ]
        )
    }

    func requestHealthAccess() {
        runDoctor()

        guard !isUITestMockHealthDataAvailable else {
            authorizationState = "granted"
            lastUpdated = Self.isoTimestamp(Date())
            appendLog(
                title: "requestHealthAccess",
                payload: [
                    "result": authorizationState,
                    "timestamp": lastUpdated,
                ]
            )
            return
        }

        guard HKHealthStore.isHealthDataAvailable() else {
            authorizationState = "health_data_unavailable"
            appendLog(title: "requestHealthAccess", payload: ["result": authorizationState])
            return
        }

        let readTypes = readTypesForExport()
        guard !readTypes.isEmpty else {
            authorizationState = "health_types_unavailable"
            appendLog(title: "requestHealthAccess", payload: ["result": authorizationState])
            return
        }

        healthStore.requestAuthorization(toShare: [], read: readTypes) { success, error in
            Task { @MainActor in
                self.lastUpdated = Self.isoTimestamp(Date())
                if let error {
                    self.authorizationState = "error"
                    self.appendLog(
                        title: "requestHealthAccess",
                        payload: [
                            "error": error.localizedDescription,
                            "timestamp": self.lastUpdated,
                        ]
                    )
                    return
                }

                self.authorizationState = success ? "granted" : "denied"
                self.appendLog(
                    title: "requestHealthAccess",
                    payload: [
                        "result": self.authorizationState,
                        "timestamp": self.lastUpdated,
                    ]
                )
            }
        }
    }

    func requestSleepAccess() {
        requestHealthAccess()
    }

    func fetchSleepSamples(days: Int) async throws -> [SleepSampleRecord] {
        runDoctor()

        guard HKHealthStore.isHealthDataAvailable() || isUITestMockHealthDataAvailable else {
            authorizationState = "health_data_unavailable"
            appendLog(title: "fetchSleepSamples", payload: ["result": authorizationState])
            return []
        }

        guard let sleepType = HKObjectType.categoryType(forIdentifier: .sleepAnalysis) else {
            authorizationState = "sleep_type_unavailable"
            appendLog(title: "fetchSleepSamples", payload: ["result": authorizationState])
            return []
        }

        if !isUITestMockHealthDataAvailable {
            do {
                try await requestReadAuthorization(readTypes: [sleepType])
            } catch HealthKitServiceError.authorizationDenied {
                appendLog(title: "fetchSleepSamples", payload: ["result": "not_authorized"])
                return []
            }
        } else {
            authorizationState = "granted"
        }

        let now = Date()
        let startDate = Calendar.current.date(byAdding: .day, value: -days, to: now) ?? now
        let predicate = HKQuery.predicateForSamples(withStart: startDate, end: now, options: [])
        let sortDescriptors = [NSSortDescriptor(key: HKSampleSortIdentifierStartDate, ascending: true)]

        let records: [SleepSampleRecord] = try await withCheckedThrowingContinuation { continuation in
            let query = HKSampleQuery(
                sampleType: sleepType,
                predicate: predicate,
                limit: HKObjectQueryNoLimit,
                sortDescriptors: sortDescriptors
            ) { _, samples, error in
                if let error {
                    continuation.resume(throwing: error)
                    return
                }

                let categorySamples = (samples as? [HKCategorySample]) ?? []
                let records = categorySamples.map { sample in
                    SleepSampleRecord(
                        sourceID: sample.uuid.uuidString,
                        startAt: Self.isoTimestamp(sample.startDate),
                        endAt: Self.isoTimestamp(sample.endDate),
                        stage: Self.stageName(for: sample.value),
                        stageValue: Self.normalizedStageValue(for: sample.value),
                        sourceBundleID: sample.sourceRevision.source.bundleIdentifier,
                        sourceName: sample.sourceRevision.source.name,
                        metadata: [:]
                    )
                }
                continuation.resume(returning: records)
            }
            self.healthStore.execute(query)
        }

        authorizationState = "granted"
        lastUpdated = Self.isoTimestamp(now)
        appendLog(
            title: "fetchSleepSamples",
            payload: [
                "days": String(days),
                "samples": String(records.count),
                "timestamp": lastUpdated,
            ]
        )
        return records
    }

    func fetchVitalsSamples(days: Int) async throws -> [VitalsSampleRecord] {
        runDoctor()

        guard HKHealthStore.isHealthDataAvailable() || isUITestMockHealthDataAvailable else {
            authorizationState = "health_data_unavailable"
            appendLog(title: "fetchVitalsSamples", payload: ["result": authorizationState])
            return []
        }

        let configurations = vitalsQuantityConfigurations()
        guard !configurations.isEmpty else {
            authorizationState = "vitals_types_unavailable"
            appendLog(title: "fetchVitalsSamples", payload: ["result": authorizationState])
            return []
        }

        if !isUITestMockHealthDataAvailable {
            do {
                try await requestReadAuthorization(readTypes: Set(configurations.map(\.type)))
            } catch HealthKitServiceError.authorizationDenied {
                appendLog(title: "fetchVitalsSamples", payload: ["result": "not_authorized"])
                return []
            }
        } else {
            authorizationState = "granted"
        }

        var records: [VitalsSampleRecord] = []
        for configuration in configurations {
            let quantitySamples = try await fetchQuantitySamples(days: days, type: configuration.type)
            records.append(contentsOf: quantitySamples.map { sample in
                VitalsSampleRecord(
                    sourceID: sample.uuid.uuidString,
                    recordedAt: Self.isoTimestamp(sample.startDate),
                    metricType: configuration.metricType,
                    value: configuration.transform(sample.quantity),
                    unit: configuration.unitLabel,
                    sourceBundleID: sample.sourceRevision.source.bundleIdentifier,
                    sourceName: sample.sourceRevision.source.name,
                    metadata: [:]
                )
            })
        }

        let now = Date()
        authorizationState = "granted"
        lastUpdated = Self.isoTimestamp(now)
        appendLog(
            title: "fetchVitalsSamples",
            payload: [
                "days": String(days),
                "samples": String(records.count),
                "timestamp": lastUpdated,
            ]
        )
        return records.sorted { lhs, rhs in
            lhs.recordedAt < rhs.recordedAt
        }
    }

    func fetchBodySamples(days: Int) async throws -> [BodySampleRecord] {
        runDoctor()

        guard HKHealthStore.isHealthDataAvailable() || isUITestMockHealthDataAvailable else {
            authorizationState = "health_data_unavailable"
            appendLog(title: "fetchBodySamples", payload: ["result": authorizationState])
            return []
        }

        let quantityConfigurations = bodyQuantityConfigurations()
        var readTypes = Set(quantityConfigurations.map(\.type))
        if let systolicType = HKObjectType.quantityType(forIdentifier: .bloodPressureSystolic) {
            readTypes.insert(systolicType)
        }
        if let diastolicType = HKObjectType.quantityType(forIdentifier: .bloodPressureDiastolic) {
            readTypes.insert(diastolicType)
        }
        guard !readTypes.isEmpty else {
            authorizationState = "body_types_unavailable"
            appendLog(title: "fetchBodySamples", payload: ["result": authorizationState])
            return []
        }

        if !isUITestMockHealthDataAvailable {
            do {
                try await requestReadAuthorization(readTypes: readTypes)
            } catch HealthKitServiceError.authorizationDenied {
                appendLog(title: "fetchBodySamples", payload: ["result": "not_authorized"])
                return []
            }
        } else {
            authorizationState = "granted"
        }

        var records: [BodySampleRecord] = []
        for configuration in quantityConfigurations {
            let quantitySamples = try await fetchQuantitySamples(days: days, type: configuration.type)
            records.append(contentsOf: quantitySamples.map { sample in
                BodySampleRecord(
                    sourceID: sample.uuid.uuidString,
                    recordedAt: Self.isoTimestamp(sample.startDate),
                    metricType: configuration.metricType,
                    value: configuration.transform(sample.quantity),
                    unit: configuration.unitLabel,
                    sourceBundleID: sample.sourceRevision.source.bundleIdentifier,
                    sourceName: sample.sourceRevision.source.name,
                    metadata: [:]
                )
            })
        }

        if let bloodPressureType = HKObjectType.correlationType(forIdentifier: .bloodPressure) {
            let bloodPressureSamples = try await fetchBloodPressureSamples(days: days, type: bloodPressureType)
            records.append(contentsOf: bloodPressureSamples)
        }

        let now = Date()
        authorizationState = "granted"
        lastUpdated = Self.isoTimestamp(now)
        appendLog(
            title: "fetchBodySamples",
            payload: [
                "days": String(days),
                "samples": String(records.count),
                "timestamp": lastUpdated,
            ]
        )
        return records.sorted { lhs, rhs in
            if lhs.recordedAt == rhs.recordedAt {
                return lhs.sourceID < rhs.sourceID
            }
            return lhs.recordedAt < rhs.recordedAt
        }
    }

    func fetchLifestyleSamples(days: Int) async throws -> [LifestyleSampleRecord] {
        runDoctor()

        guard HKHealthStore.isHealthDataAvailable() || isUITestMockHealthDataAvailable else {
            authorizationState = "health_data_unavailable"
            appendLog(title: "fetchLifestyleSamples", payload: ["result": authorizationState])
            return []
        }

        let configurations = lifestyleQuantityConfigurations()
        guard !configurations.isEmpty else {
            authorizationState = "lifestyle_types_unavailable"
            appendLog(title: "fetchLifestyleSamples", payload: ["result": authorizationState])
            return []
        }

        if !isUITestMockHealthDataAvailable {
            do {
                try await requestReadAuthorization(readTypes: Set(configurations.map(\.type)))
            } catch HealthKitServiceError.authorizationDenied {
                appendLog(title: "fetchLifestyleSamples", payload: ["result": "not_authorized"])
                return []
            }
        } else {
            authorizationState = "granted"
        }

        var records: [LifestyleSampleRecord] = []
        for configuration in configurations {
            let quantitySamples = try await fetchQuantitySamples(days: days, type: configuration.type)
            records.append(contentsOf: quantitySamples.map { sample in
                LifestyleSampleRecord(
                    sourceID: sample.uuid.uuidString,
                    recordedAt: Self.isoTimestamp(sample.startDate),
                    metricType: configuration.metricType,
                    value: configuration.transform(sample.quantity),
                    unit: configuration.unitLabel,
                    sourceBundleID: sample.sourceRevision.source.bundleIdentifier,
                    sourceName: sample.sourceRevision.source.name,
                    metadata: [:]
                )
            })
        }

        let now = Date()
        authorizationState = "granted"
        lastUpdated = Self.isoTimestamp(now)
        appendLog(
            title: "fetchLifestyleSamples",
            payload: [
                "days": String(days),
                "samples": String(records.count),
                "timestamp": lastUpdated,
            ]
        )
        return records.sorted { lhs, rhs in
            lhs.recordedAt < rhs.recordedAt
        }
    }

    func fetchActivitySamples(days: Int) async throws -> [ActivitySampleRecord] {
        runDoctor()

        guard HKHealthStore.isHealthDataAvailable() || isUITestMockHealthDataAvailable else {
            authorizationState = "health_data_unavailable"
            appendLog(title: "fetchActivitySamples", payload: ["result": authorizationState])
            return []
        }

        guard let stepCountType = HKObjectType.quantityType(forIdentifier: .stepCount) else {
            authorizationState = "activity_type_unavailable"
            appendLog(title: "fetchActivitySamples", payload: ["result": authorizationState])
            return []
        }

        if !isUITestMockHealthDataAvailable {
            do {
                try await requestReadAuthorization(readTypes: [stepCountType])
            } catch HealthKitServiceError.authorizationDenied {
                appendLog(title: "fetchActivitySamples", payload: ["result": "not_authorized"])
                return []
            }
        } else {
            authorizationState = "granted"
        }

        let quantitySamples = try await fetchQuantitySamples(days: days, type: stepCountType)
        let records = quantitySamples.map { sample in
            ActivitySampleRecord(
                sourceID: sample.uuid.uuidString,
                startAt: Self.isoTimestamp(sample.startDate),
                endAt: Self.isoTimestamp(sample.endDate),
                metricType: "step_count",
                value: sample.quantity.doubleValue(for: .count()),
                unit: "count",
                sourceBundleID: sample.sourceRevision.source.bundleIdentifier,
                sourceName: sample.sourceRevision.source.name,
                metadata: [:]
            )
        }

        let now = Date()
        authorizationState = "granted"
        lastUpdated = Self.isoTimestamp(now)
        appendLog(
            title: "fetchActivitySamples",
            payload: [
                "days": String(days),
                "samples": String(records.count),
                "timestamp": lastUpdated,
            ]
        )
        return records
    }

    func fetchWorkoutSamples(days: Int) async throws -> [WorkoutRecord] {
        runDoctor()

        guard HKHealthStore.isHealthDataAvailable() || isUITestMockHealthDataAvailable else {
            authorizationState = "health_data_unavailable"
            appendLog(title: "fetchWorkoutSamples", payload: ["result": authorizationState])
            return []
        }

        let workoutType = HKWorkoutType.workoutType()

        if !isUITestMockHealthDataAvailable {
            do {
                try await requestReadAuthorization(readTypes: [workoutType])
            } catch HealthKitServiceError.authorizationDenied {
                appendLog(title: "fetchWorkoutSamples", payload: ["result": "not_authorized"])
                return []
            }
        } else {
            authorizationState = "granted"
        }

        let now = Date()
        let startDate = Calendar.current.date(byAdding: .day, value: -days, to: now) ?? now
        let predicate = HKQuery.predicateForSamples(withStart: startDate, end: now, options: [])
        let sortDescriptors = [NSSortDescriptor(key: HKSampleSortIdentifierStartDate, ascending: true)]

        let workouts: [HKWorkout] = try await withCheckedThrowingContinuation { continuation in
            let query = HKSampleQuery(
                sampleType: workoutType,
                predicate: predicate,
                limit: HKObjectQueryNoLimit,
                sortDescriptors: sortDescriptors
            ) { _, samples, error in
                if let error {
                    continuation.resume(throwing: error)
                    return
                }

                continuation.resume(returning: (samples as? [HKWorkout]) ?? [])
            }
            self.healthStore.execute(query)
        }

        let records = workouts.map { workout in
            WorkoutRecord(
                source_id: workout.uuid.uuidString,
                workout_type: workout.workoutActivityType.exportName,
                start_at: Self.isoTimestamp(workout.startDate),
                end_at: Self.isoTimestamp(workout.endDate),
                duration_seconds: workout.duration,
                total_energy_burned: workout.totalEnergyBurned?.doubleValue(for: .kilocalorie()),
                total_distance_meters: workout.totalDistance?.doubleValue(for: .meter()),
                source_bundle_id: workout.sourceRevision.source.bundleIdentifier,
                source_name: workout.sourceRevision.source.name,
                metadata: [:]
            )
        }

        authorizationState = "granted"
        lastUpdated = Self.isoTimestamp(now)
        appendLog(
            title: "fetchWorkoutSamples",
            payload: [
                "days": String(days),
                "samples": String(records.count),
                "timestamp": lastUpdated,
            ]
        )
        return records
    }

    nonisolated static func stageName(for rawValue: Int) -> String {
        guard let stage = HKCategoryValueSleepAnalysis(rawValue: rawValue) else {
            return "unknown"
        }

        switch stage {
        case .inBed:
            return "in_bed"
        case .awake:
            return "awake"
        case .asleepCore:
            return "asleep_core"
        case .asleepDeep:
            return "asleep_deep"
        case .asleepREM:
            return "asleep_rem"
        case .asleepUnspecified:
            return "asleep_unspecified"
        @unknown default:
            return "unknown"
        }
    }

    nonisolated static func normalizedStageValue(for rawValue: Int) -> Int {
        guard let stage = HKCategoryValueSleepAnalysis(rawValue: rawValue) else {
            return rawValue
        }

        switch stage {
        case .inBed:
            return 0
        case .awake:
            return 1
        case .asleepCore:
            return 2
        case .asleepDeep:
            return 3
        case .asleepREM:
            return 4
        case .asleepUnspecified:
            return 5
        @unknown default:
            return rawValue
        }
    }

    nonisolated static func isoTimestamp(_ date: Date) -> String {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime]
        formatter.timeZone = TimeZone(secondsFromGMT: 0)
        return formatter.string(from: date)
    }

    private var isUITestMockHealthDataAvailable: Bool {
        processInfo.arguments.contains("UITEST_HEALTH_DATA_AVAILABLE_TRUE")
    }

    private func requestReadAuthorization(readTypes: Set<HKObjectType>) async throws {
        try await withCheckedThrowingContinuation { (continuation: CheckedContinuation<Void, Error>) in
            healthStore.requestAuthorization(toShare: [], read: readTypes) { success, error in
                if let error {
                    continuation.resume(throwing: error)
                    return
                }
                if success {
                    continuation.resume(returning: ())
                    return
                }
                continuation.resume(throwing: HealthKitServiceError.authorizationDenied)
            }
        }
    }

    private func fetchQuantitySamples(days: Int, type: HKQuantityType) async throws -> [HKQuantitySample] {
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

                continuation.resume(returning: (samples as? [HKQuantitySample]) ?? [])
            }
            self.healthStore.execute(query)
        }
    }

    private func fetchBloodPressureSamples(days: Int, type: HKCorrelationType) async throws -> [BodySampleRecord] {
        let now = Date()
        let startDate = Calendar.current.date(byAdding: .day, value: -days, to: now) ?? now
        let predicate = HKQuery.predicateForSamples(withStart: startDate, end: now, options: [])
        let sortDescriptors = [NSSortDescriptor(key: HKSampleSortIdentifierStartDate, ascending: true)]

        let correlations: [HKCorrelation] = try await withCheckedThrowingContinuation { continuation in
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

                continuation.resume(returning: (samples as? [HKCorrelation]) ?? [])
            }
            self.healthStore.execute(query)
        }

        guard
            let systolicType = HKObjectType.quantityType(forIdentifier: .bloodPressureSystolic),
            let diastolicType = HKObjectType.quantityType(forIdentifier: .bloodPressureDiastolic)
        else {
            return []
        }

        var records: [BodySampleRecord] = []
        for correlation in correlations {
            let recordedAt = Self.isoTimestamp(correlation.startDate)
            let sourceID = correlation.uuid.uuidString
            let sourceBundleID = correlation.sourceRevision.source.bundleIdentifier
            let sourceName = correlation.sourceRevision.source.name

            if let systolicSample = correlation.objects(for: systolicType).first as? HKQuantitySample {
                records.append(
                    BodySampleRecord(
                        sourceID: sourceID,
                        recordedAt: recordedAt,
                        metricType: "blood_pressure_systolic",
                        value: systolicSample.quantity.doubleValue(for: .millimeterOfMercury()),
                        unit: "mmHg",
                        sourceBundleID: sourceBundleID,
                        sourceName: sourceName,
                        metadata: [:]
                    )
                )
            }

            if let diastolicSample = correlation.objects(for: diastolicType).first as? HKQuantitySample {
                records.append(
                    BodySampleRecord(
                        sourceID: sourceID,
                        recordedAt: recordedAt,
                        metricType: "blood_pressure_diastolic",
                        value: diastolicSample.quantity.doubleValue(for: .millimeterOfMercury()),
                        unit: "mmHg",
                        sourceBundleID: sourceBundleID,
                        sourceName: sourceName,
                        metadata: [:]
                    )
                )
            }
        }

        return records
    }

    private func readTypesForExport() -> Set<HKObjectType> {
        var readTypes: Set<HKObjectType> = []

        if let sleepType = HKObjectType.categoryType(forIdentifier: .sleepAnalysis) {
            readTypes.insert(sleepType)
        }

        for configuration in vitalsQuantityConfigurations() {
            readTypes.insert(configuration.type)
        }
        for configuration in bodyQuantityConfigurations() {
            readTypes.insert(configuration.type)
        }
        for configuration in lifestyleQuantityConfigurations() {
            readTypes.insert(configuration.type)
        }
        // Blood pressure: request authorization for the individual quantity types,
        // NOT the correlation type (HealthKit disallows auth requests on HKCorrelationType)
        if let systolicType = HKObjectType.quantityType(forIdentifier: .bloodPressureSystolic) {
            readTypes.insert(systolicType)
        }
        if let diastolicType = HKObjectType.quantityType(forIdentifier: .bloodPressureDiastolic) {
            readTypes.insert(diastolicType)
        }
        if let stepCountType = HKObjectType.quantityType(forIdentifier: .stepCount) {
            readTypes.insert(stepCountType)
        }
        readTypes.insert(HKWorkoutType.workoutType())

        return readTypes
    }

    private func vitalsQuantityConfigurations() -> [QuantitySampleConfiguration] {
        [
            quantityConfiguration(identifier: .restingHeartRate, metricType: "resting_heart_rate", unitLabel: "count/min") { quantity in
                quantity.doubleValue(for: HKUnit.count().unitDivided(by: .minute()))
            },
            quantityConfiguration(identifier: .heartRate, metricType: "heart_rate", unitLabel: "count/min") { quantity in
                quantity.doubleValue(for: HKUnit.count().unitDivided(by: .minute()))
            },
            quantityConfiguration(identifier: .heartRateVariabilitySDNN, metricType: "heart_rate_variability_sdnn", unitLabel: "ms") { quantity in
                quantity.doubleValue(for: HKUnit.secondUnit(with: .milli))
            },
            quantityConfiguration(identifier: .respiratoryRate, metricType: "respiratory_rate", unitLabel: "count/min") { quantity in
                quantity.doubleValue(for: HKUnit.count().unitDivided(by: .minute()))
            },
            quantityConfiguration(identifier: .oxygenSaturation, metricType: "oxygen_saturation", unitLabel: "%") { quantity in
                quantity.doubleValue(for: .percent()) * 100.0
            },
            quantityConfiguration(identifier: .activeEnergyBurned, metricType: "active_energy_burned", unitLabel: "kcal") { quantity in
                quantity.doubleValue(for: .kilocalorie())
            },
        ].compactMap { $0 }
    }

    private func bodyQuantityConfigurations() -> [QuantitySampleConfiguration] {
        [
            quantityConfiguration(identifier: .bodyMass, metricType: "body_mass", unitLabel: "kg") { quantity in
                quantity.doubleValue(for: HKUnit.gramUnit(with: .kilo))
            },
            quantityConfiguration(identifier: .bloodGlucose, metricType: "blood_glucose", unitLabel: "mg/dL") { quantity in
                quantity.doubleValue(for: HKUnit(from: "mg/dL"))
            },
        ].compactMap { $0 }
    }

    private func lifestyleQuantityConfigurations() -> [QuantitySampleConfiguration] {
        [
            quantityConfiguration(identifier: .dietaryCaffeine, metricType: "dietary_caffeine", unitLabel: "mg") { quantity in
                quantity.doubleValue(for: HKUnit.gramUnit(with: .milli))
            },
            quantityConfiguration(identifierRawValue: "HKQuantityTypeIdentifierDietaryAlcohol", metricType: "dietary_alcohol", unitLabel: "g") { quantity in
                quantity.doubleValue(for: .gram())
            },
        ].compactMap { $0 }
    }

    private func quantityConfiguration(
        identifier: HKQuantityTypeIdentifier,
        metricType: String,
        unitLabel: String,
        transform: @escaping (HKQuantity) -> Double
    ) -> QuantitySampleConfiguration? {
        guard let type = HKObjectType.quantityType(forIdentifier: identifier) else {
            return nil
        }
        return QuantitySampleConfiguration(type: type, metricType: metricType, unitLabel: unitLabel, transform: transform)
    }

    private func quantityConfiguration(
        identifierRawValue: String,
        metricType: String,
        unitLabel: String,
        transform: @escaping (HKQuantity) -> Double
    ) -> QuantitySampleConfiguration? {
        quantityConfiguration(
            identifier: HKQuantityTypeIdentifier(rawValue: identifierRawValue),
            metricType: metricType,
            unitLabel: unitLabel,
            transform: transform
        )
    }

    private func appendLog(title: String, payload: [String: String]) {
        let data = try? JSONSerialization.data(withJSONObject: payload, options: [.prettyPrinted, .sortedKeys])
        let text = String(data: data ?? Data("{}".utf8), encoding: .utf8) ?? "{}"
        let block = "[\(title)]\n\(text)"
        logEntries.append(block)
        print(block)
    }
}

private struct QuantitySampleConfiguration {
    let type: HKQuantityType
    let metricType: String
    let unitLabel: String
    let transform: (HKQuantity) -> Double
}

private extension HKWorkoutActivityType {
    var exportName: String {
        switch self {
        case .americanFootball:
            return "americanFootball"
        case .archery:
            return "archery"
        case .australianFootball:
            return "australianFootball"
        case .badminton:
            return "badminton"
        case .baseball:
            return "baseball"
        case .basketball:
            return "basketball"
        case .bowling:
            return "bowling"
        case .boxing:
            return "boxing"
        case .climbing:
            return "climbing"
        case .crossTraining:
            return "crossTraining"
        case .cricket:
            return "cricket"
        case .curling:
            return "curling"
        case .cycling:
            return "cycling"
        case .dance:
            return "dance"
        case .danceInspiredTraining:
            return "danceInspiredTraining"
        case .elliptical:
            return "elliptical"
        case .equestrianSports:
            return "equestrianSports"
        case .fencing:
            return "fencing"
        case .fishing:
            return "fishing"
        case .functionalStrengthTraining:
            return "functionalStrengthTraining"
        case .golf:
            return "golf"
        case .gymnastics:
            return "gymnastics"
        case .handball:
            return "handball"
        case .hiking:
            return "hiking"
        case .hockey:
            return "hockey"
        case .hunting:
            return "hunting"
        case .lacrosse:
            return "lacrosse"
        case .martialArts:
            return "martialArts"
        case .mindAndBody:
            return "mindAndBody"
        case .mixedMetabolicCardioTraining:
            return "mixedMetabolicCardioTraining"
        case .paddleSports:
            return "paddleSports"
        case .play:
            return "play"
        case .preparationAndRecovery:
            return "preparationAndRecovery"
        case .racquetball:
            return "racquetball"
        case .rowing:
            return "rowing"
        case .rugby:
            return "rugby"
        case .running:
            return "running"
        case .sailing:
            return "sailing"
        case .skatingSports:
            return "skatingSports"
        case .snowSports:
            return "snowSports"
        case .soccer:
            return "soccer"
        case .softball:
            return "softball"
        case .squash:
            return "squash"
        case .stairClimbing:
            return "stairClimbing"
        case .surfingSports:
            return "surfingSports"
        case .swimming:
            return "swimming"
        case .tableTennis:
            return "tableTennis"
        case .tennis:
            return "tennis"
        case .trackAndField:
            return "trackAndField"
        case .traditionalStrengthTraining:
            return "traditionalStrengthTraining"
        case .volleyball:
            return "volleyball"
        case .walking:
            return "walking"
        case .waterFitness:
            return "waterFitness"
        case .waterPolo:
            return "waterPolo"
        case .waterSports:
            return "waterSports"
        case .wrestling:
            return "wrestling"
        case .yoga:
            return "yoga"
        case .barre:
            return "barre"
        case .coreTraining:
            return "coreTraining"
        case .crossCountrySkiing:
            return "crossCountrySkiing"
        case .downhillSkiing:
            return "downhillSkiing"
        case .flexibility:
            return "flexibility"
        case .highIntensityIntervalTraining:
            return "HIIT"
        case .jumpRope:
            return "jumpRope"
        case .kickboxing:
            return "kickboxing"
        case .pilates:
            return "pilates"
        case .snowboarding:
            return "snowboarding"
        case .stairs:
            return "stairs"
        case .stepTraining:
            return "stepTraining"
        case .wheelchairWalkPace:
            return "wheelchairWalkPace"
        case .wheelchairRunPace:
            return "wheelchairRunPace"
        case .taiChi:
            return "taiChi"
        case .mixedCardio:
            return "mixedCardio"
        case .handCycling:
            return "handCycling"
        case .discSports:
            return "discSports"
        case .fitnessGaming:
            return "fitnessGaming"
        case .cardioDance:
            return "cardioDance"
        case .socialDance:
            return "socialDance"
        case .pickleball:
            return "pickleball"
        case .cooldown:
            return "cooldown"
        case .swimBikeRun:
            return "swimBikeRun"
        case .transition:
            return "transition"
        case .underwaterDiving:
            return "underwaterDiving"
        case .other:
            return "other"
        @unknown default:
            return "other_\(rawValue)"
        }
    }
}

enum HealthKitServiceError: LocalizedError {
    case authorizationDenied

    var errorDescription: String? {
        switch self {
        case .authorizationDenied:
            return "HealthKit authorization was not granted."
        }
    }
}
