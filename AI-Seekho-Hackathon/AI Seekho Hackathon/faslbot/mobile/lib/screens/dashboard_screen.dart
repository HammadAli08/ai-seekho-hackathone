import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:glassmorphism/glassmorphism.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import 'dart:ui' as ui;
import '../config/api_config.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  bool _isLoading = false;
  List<dynamic> _insights = [];

  @override
  void initState() {
    super.initState();
    _fetchInsights();
  }

  Future<void> _fetchInsights() async {
    try {
      final response = await http.get(Uri.parse('${ApiConfig.baseUrl}/insights'));
      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        if (mounted) {
          setState(() {
            _insights = data['data'];
          });
        }
      }
    } catch (e) {
      debugPrint("Failed to fetch insights: $e");
    }
  }

  Future<void> _triggerPipeline() async {
    setState(() => _isLoading = true);

    try {
      final response = await http.post(
        Uri.parse('${ApiConfig.baseUrl}/trigger-pipeline'),
        headers: {'Content-Type': 'application/json'},
      ).timeout(const Duration(seconds: 30));

      if (mounted) {
        if (response.statusCode == 200 || response.statusCode == 202) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Row(
                children: [
                  const Icon(Icons.check_circle, color: Color(0xFF00FFA3)),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      'AI Market Analysis Started! Check backend for progress.',
                      style: const TextStyle(color: Colors.white),
                    ),
                  ),
                ],
              ),
              backgroundColor: const Color(0xFF121A2E),
              behavior: SnackBarBehavior.floating,
              duration: const Duration(seconds: 4),
            ),
          );
          // Auto-refresh the dashboard after pipeline finishes
          Future.delayed(const Duration(seconds: 5), () {
            _fetchInsights();
          });
        } else {
          _showErrorSnackBar('Server returned: ${response.statusCode}');
        }
      }
    } catch (e) {
      if (mounted) {
        _showErrorSnackBar('Could not connect to backend. Is it running?');
      }
    } finally {
      if (mounted) {
        setState(() => _isLoading = false);
      }
    }
  }

  void _showErrorSnackBar(String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Row(
          children: [
            const Icon(Icons.error_outline, color: Colors.redAccent),
            const SizedBox(width: 12),
            Expanded(
              child: Text(message, style: const TextStyle(color: Colors.white)),
            ),
          ],
        ),
        backgroundColor: const Color(0xFF121A2E),
        behavior: SnackBarBehavior.floating,
      ),
    );
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
            SliverToBoxAdapter(
              child: _buildFAB(),
            ),
            SliverToBoxAdapter(
              child: _buildInsightsSection(),
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
              Container(
                width: 8,
                height: 8,
                decoration: const BoxDecoration(
                  color: Color(0xFF00FFA3),
                  shape: BoxShape.circle,
                  boxShadow: [
                    BoxShadow(
                      color: Color(0xFF00FFA3),
                      blurRadius: 12,
                      spreadRadius: 2,
                    ),
                  ],
                ),
              ).animate().fade(duration: 600.ms).scale(),
              const SizedBox(width: 12),
              Text(
                'FaslBot',
                style: Theme.of(context).textTheme.headlineLarge?.copyWith(
                      color: const Color(0xFF00FFA3),
                      fontWeight: FontWeight.bold,
                    ),
              ).animate().fade(delay: 200.ms).slideX(begin: -0.2),
              Text(
                ' (فصل بوٹ)',
                style: Theme.of(context).textTheme.headlineLarge?.copyWith(
                      color: const Color(0xFFFFD700),
                      fontWeight: FontWeight.w300,
                    ),
              ).animate().fade(delay: 300.ms).slideX(begin: -0.2),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            'Live Market Intelligence',
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  color: Colors.white54,
                  letterSpacing: 1.2,
                ),
          ).animate().fade(delay: 400.ms),
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
          ).animate().fade(delay: 500.ms).scaleX(begin: 0),
        ],
      ),
    );
  }

  Widget _buildFAB() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
      child: GestureDetector(
        onTap: _isLoading ? null : _triggerPipeline,
        child: Container(
          height: 64,
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(16),
            gradient: const LinearGradient(
              colors: [Color(0xFF00FFA3), Color(0xFF00D68F)],
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
            ),
            boxShadow: [
              BoxShadow(
                color: const Color(0xFF00FFA3).withOpacity(0.4),
                blurRadius: 20,
                offset: const Offset(0, 8),
              ),
            ],
          ),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              if (_isLoading)
                const SizedBox(
                  width: 24,
                  height: 24,
                  child: CircularProgressIndicator(
                    strokeWidth: 2.5,
                    valueColor: AlwaysStoppedAnimation<Color>(Color(0xFF0A0E17)),
                  ),
                )
              else
                const Icon(
                  Icons.psychology_outlined,
                  color: Color(0xFF0A0E17),
                  size: 28,
                ),
              const SizedBox(width: 12),
              Text(
                _isLoading ? 'Processing...' : 'Run AI Market Analysis',
                style: const TextStyle(
                  color: Color(0xFF0A0E17),
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                  letterSpacing: 0.5,
                ),
              ),
            ],
          ),
        ),
      ),
    ).animate().fade(delay: 600.ms).slideY(begin: 0.3).scale();
  }

  Widget _buildInsightsSection() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(24, 24, 24, 0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(
                Icons.insights,
                color: Color(0xFFFFD700),
                size: 24,
              ),
              const SizedBox(width: 10),
              Text(
                'Latest Insights',
                style: Theme.of(context).textTheme.titleLarge?.copyWith(
                      color: Colors.white,
                    ),
              ),
            ],
          ).animate().fade(delay: 700.ms),
          const SizedBox(height: 16),
          if (_insights.isEmpty)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 20),
              child: Center(
                child: Text('No insights generated yet. Click the button above to run analysis.', style: TextStyle(color: Colors.white54)),
              ),
            )
          else
            ..._insights.asMap().entries.map((entry) {
              int index = entry.key;
              var run = entry.value;
              var insight = run['insight'] ?? {};
              var delayMs = 800 + (index * 100);
              
              String type = insight['type']?.toString().toUpperCase().replaceAll('_', ' ') ?? 'INFO';
              if (type.length > 15) type = type.substring(0, 15);
              
              String headline = insight['headline'] ?? 'Analysis Complete';
              String detail = insight['key_metric'] ?? '';
              String detailUrdu = insight['headline_urdu'] ?? '';
              String metric = 'Urgency: ${insight['urgency']?.toString().toUpperCase() ?? 'MEDIUM'}';
              
              IconData icon = Icons.trending_up;
              if (type.contains('SPIKE') || type.contains('ALERT')) icon = Icons.warning_amber_rounded;
              if (type.contains('NEWS') || type.contains('DISRUPTION')) icon = Icons.newspaper;
              
              return Padding(
                padding: const EdgeInsets.only(bottom: 16),
                child: _buildInsightCard(
                  type: type,
                  icon: icon,
                  headline: headline,
                  detail: detail,
                  detailUrdu: detailUrdu,
                  metric: metric,
                  delay: delayMs,
                ),
              );
            }),
        ],
      ),
    );
  }

  Widget _buildInsightCard({
    required String type,
    required IconData icon,
    required String headline,
    required String detail,
    required String detailUrdu,
    required String metric,
    required int delay,
  }) {
    Color typeColor;
    switch (type) {
      case 'CRITICAL':
        typeColor = const Color(0xFFFF4757);
        break;
      case 'ALERT':
        typeColor = const Color(0xFFFFD700);
        break;
      default:
        typeColor = const Color(0xFF00FFA3);
    }

    return ClipRRect(
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
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    color: typeColor.withOpacity(0.2),
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: typeColor.withOpacity(0.5)),
                  ),
                  child: Text(
                    type,
                    style: TextStyle(
                      color: typeColor,
                      fontSize: 11,
                      fontWeight: FontWeight.bold,
                      letterSpacing: 1,
                    ),
                  ),
                ),
                const Spacer(),
                Icon(icon, color: typeColor, size: 24),
              ],
            ),
            const SizedBox(height: 12),
            Text(
              headline,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(
                color: Colors.white,
                fontSize: 16,
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: 6),
            Text(
              detail,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(
                color: Colors.white.withOpacity(0.6),
                fontSize: 13,
              ),
            ),
            const SizedBox(height: 8),
            Row(
              children: [
                Expanded(
                  child: Text(
                    detailUrdu,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                      color: Colors.white.withOpacity(0.4),
                      fontSize: 11,
                      fontStyle: FontStyle.italic,
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: const Color(0xFF00FFA3).withOpacity(0.15),
                    borderRadius: BorderRadius.circular(6),
                  ),
                  child: Text(
                    metric,
                    style: const TextStyle(
                      color: Color(0xFF00FFA3),
                      fontSize: 11,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    ))).animate().fade(delay: Duration(milliseconds: delay)).slideY(begin: 0.2).scale(begin: const Offset(0.95, 0.95));
  }
}