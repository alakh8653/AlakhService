import 'package:dio/dio.dart';

import '../../../core/constants/api_constants.dart';
import '../../../core/network/api_client.dart';
import '../../../core/network/api_errors.dart';

/// A request for a copy of the user's data (compliance_service). PENDING until support handles it,
/// then COMPLETED with a download link or REJECTED with a note.
class DataExportRequest {
  final String id;
  final String status;
  final String? exportUrl;
  final DateTime requestedAt;
  final DateTime? completedAt;
  final String? note;

  const DataExportRequest({
    required this.id,
    required this.status,
    this.exportUrl,
    required this.requestedAt,
    this.completedAt,
    this.note,
  });

  bool get isPending => status == 'PENDING';
  bool get isReady => status == 'COMPLETED' && (exportUrl?.isNotEmpty ?? false);

  factory DataExportRequest.fromJson(Map<String, dynamic> json) => DataExportRequest(
        id: json['id'] as String,
        status: (json['status'] as String?) ?? 'PENDING',
        exportUrl: json['export_url'] as String?,
        requestedAt: DateTime.tryParse((json['requested_at'] as String?) ?? '')?.toLocal() ?? DateTime.now(),
        completedAt: DateTime.tryParse((json['completed_at'] as String?) ?? '')?.toLocal(),
        note: json['resolution_note'] as String?,
      );
}

class DataExportApi {
  final ApiClient apiClient;

  DataExportApi(this.apiClient);

  /// The user's latest export request, or null if they never asked.
  Future<DataExportRequest?> latest() async {
    try {
      final response = await apiClient.get<List<dynamic>>(ApiConstants.dataExport);
      final all = (response.data ?? const []).map((e) => DataExportRequest.fromJson(e as Map<String, dynamic>)).toList()
        ..sort((a, b) => a.requestedAt.compareTo(b.requestedAt));
      return all.isEmpty ? null : all.last;
    } on DioException catch (e) {
      throw toServerException(e);
    }
  }

  Future<DataExportRequest> request(String userId) async {
    try {
      final response = await apiClient.post<Map<String, dynamic>>(ApiConstants.dataExport, data: {'user_id': userId});
      return DataExportRequest.fromJson(response.data!);
    } on DioException catch (e) {
      throw toServerException(e);
    }
  }
}
