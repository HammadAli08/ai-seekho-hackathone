import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'dart:ui' as ui;
import 'dart:convert';
import 'package:http/http.dart' as http;
import '../config/api_config.dart';

class ActionLogScreen extends StatefulWidget {
  const ActionLogScreen({super.key});

  @override
  State<ActionLogScreen> createState() => _ActionLogScreenState();
}

class _ActionLogScreenState extends State<ActionLogScreen> {
  List<Map<String, dynamic>> _actions = [];
  bool _isLoading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _fetchActions();
  }

  Future<void> _fetchActions() async {
    try {
      final response = await http.get(
        Uri.parse('${ApiConfig.baseUrl}/actions'),
      ).timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        if (mounted) {
          setState(() {
            _actions = List<Map<String, dynamic>>.from(data['data'] ?? []);
            _isLoading = false;
          });
        }
      } else {
        setState(() {
          _error = 'Server error: ${response.statusCode}';
          _isLoading = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = 'Could not connect to backend';
          _isLoading = false;
        });
      }
    }
  }

  String _formatTimestamp(String? timestamp) {
    if (timestamp == null) return 'Unknown time';
    try {
      final dt = DateTime.parse(timestamp);
      return '${dt.day}/${dt.month}/${dt.year} ${dt.hour.toString().padLeft(2, '0')}:${dt.minute.toString().padLeft(2, '0')}';
    } catch (e) {
      return timestamp;
    }
  }

  IconData _getActionIcon(String? actionType) {
    switch (actionType) {
      case 'TELENOR_SMS_BLAST':
        return Icons.sms;
      case 'MANDI_PRICE_UPDATE':
        return Icons.update;
      case 'PROCUREMENT_ADVISORY':
        return Icons.local_shipping;
      default:
        return Icons.notifications;
    }
  }

  Color _getActionColor(String? actionType) {
    switch (actionType) {
      case 'TELENOR_SMS_BLAST':
        return const Color(0xFF00FFA3);
      case 'MANDI_PRICE_UPDATE':
        return const Color(0xFFFFD700);
      case 'PROCUREMENT_ADVISORY':
        return const Color(0xFF4FC3F7);
      default:
        return Colors.white70;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0A0E17),
      body: SafeArea(
        child: CustomScrollView(
          slivers: [
            SliverToBoxAdapter(
              child: _buildHeader(),
            ),
            if (_isLoading)
              const SliverFillRemaining(
                child: Center(
                  child: CircularProgressIndicator(color: Color(0xFF00FFA3)),
                ),
              )
            else if (_error != null)
              SliverFillRemaining(
                child: Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(Icons.wifi_off, color: Colors.white38, size: 48),
                      const SizedBox(height: 16),
                      Text(_error!, style: TextStyle(color: Colors.white54)),
                      const SizedBox(height: 16),
                      TextButton(
                        onPressed: _fetchActions,
                        child: const Text('Retry', style: TextStyle(color: Color(0xFF00FFA3))),
                      ),
                    ],
                  ),
                ),
              )
            else if (_actions.isEmpty)
              SliverFillRemaining(
                child: Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(Icons.inbox_outlined, color: Colors.white38, size: 64),
                      const SizedBox(height: 16),
                      const Text(
                        'No actions executed yet',
                        style: TextStyle(color: Colors.white54, fontSize: 16),
                      ),
                      const SizedBox(height: 8),
                      Text(
                        'Run the pipeline to generate insights',
                        style: TextStyle(color: Colors.white38, fontSize: 13),
                      ),
                    ],
                  ),
                ),
              )
            else
              SliverPadding(
                padding: const EdgeInsets.all(16),
                sliver: SliverList(
                  delegate: SliverChildBuilderDelegate(
                    (context, index) => _buildActionCard(_actions[index], index),
                    childCount: _actions.length,
                  ),
                ),
              ),
            const SliverToBoxAdapter(
              child: SizedBox(height: 100),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildHeader() {
    return Container(
      padding: const EdgeInsets.fromLTRB(24, 20, 24, 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.history, color: Color(0xFF00FFA3), size: 28),
              const SizedBox(width: 12),
              Text(
                'Action Logs',
                style: Theme.of(context).textTheme.headlineLarge?.copyWith(
                      color: Colors.white,
                      fontWeight: FontWeight.bold,
                    ),
              ).animate().fade(duration: 600.ms).slideX(begin: -0.2),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            'SMS alerts sent by FaslBot',
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  color: Colors.white54,
                  letterSpacing: 1.2,
                ),
          ).animate().fade(delay: 200.ms),
          const SizedBox(height: 20),
          Container(
            height: 1,
            decoration: BoxDecoration(
              gradient: LinearGradient(
                colors: [
                  const Color(0xFF00FFA3).withOpacity(0),
                  const Color(0xFF00FFA3).withOpacity(0.5),
                  const Color(0xFFFFD700).withOpacity(0.3),
                  const Color(0xFFFFD700).withOpacity(0),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildActionCard(Map<String, dynamic> action, int index) {
    final delayMs = 200 + (index * 100);
    final actionType = action['action_type']?.toString() ?? 'UNKNOWN';
    final actionColor = _getActionColor(actionType);
    final actionIcon = _getActionIcon(actionType);
    final message = action['message']?.toString() ?? 'No message content';
    final city = action['city']?.toString() ?? 'Unknown';
    final timestamp = action['timestamp']?.toString();
    final titleUrdu = action['title_urdu']?.toString() ?? '';
    final recipientCount = action['recipient_count'] ?? 0;
    final status = action['status']?.toString() ?? 'unknown';

    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(20),
        child: BackdropFilter(
          filter: ui.ImageFilter.blur(sigmaX: 15, sigmaY: 15),
          child: Container(
            width: double.infinity,
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(20),
              border: Border.all(color: Colors.white.withOpacity(0.15), width: 1),
              gradient: LinearGradient(
                colors: [Colors.white.withOpacity(0.07), Colors.white.withOpacity(0.03)],
              ),
            ),
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Container(
                        padding: const EdgeInsets.all(10),
                        decoration: BoxDecoration(
                          color: actionColor.withOpacity(0.15),
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: Icon(actionIcon, color: actionColor, size: 24),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              titleUrdu,
                              style: const TextStyle(
                                color: Colors.white,
                                fontSize: 16,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                            const SizedBox(height: 2),
                            Text(
                              '$city • $recipientCount recipients',
                              style: TextStyle(
                                color: Colors.white.withOpacity(0.5),
                                fontSize: 12,
                              ),
                            ),
                          ],
                        ),
                      ),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                        decoration: BoxDecoration(
                          color: status == 'success'
                              ? const Color(0xFF00FFA3).withOpacity(0.2)
                              : Colors.orange.withOpacity(0.2),
                          borderRadius: BorderRadius.circular(6),
                        ),
                        child: Text(
                          status.toUpperCase(),
                          style: TextStyle(
                            color: status == 'success' ? const Color(0xFF00FFA3) : Colors.orange,
                            fontSize: 10,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: actionColor.withOpacity(0.08),
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: actionColor.withOpacity(0.2)),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Icon(Icons.sms, color: actionColor, size: 14),
                            const SizedBox(width: 6),
                            Text(
                              'SMS Message',
                              style: TextStyle(
                                color: actionColor,
                                fontSize: 11,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 8),
                        Text(
                          message,
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 14,
                            height: 1.4,
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 8),
                  Row(
                    children: [
                      Icon(Icons.access_time, color: Colors.white.withOpacity(0.3), size: 12),
                      const SizedBox(width: 4),
                      Text(
                        _formatTimestamp(timestamp),
                        style: TextStyle(
                          color: Colors.white.withOpacity(0.3),
                          fontSize: 11,
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
        ),
      ).animate().fade(delay: Duration(milliseconds: delayMs)).slideY(begin: 0.2),
    );
  }
}