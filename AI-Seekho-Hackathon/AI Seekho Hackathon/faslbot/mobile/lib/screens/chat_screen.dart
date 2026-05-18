import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import 'dart:ui' as ui;
import '../config/api_config.dart';

/// Premium Chat Interface for the Pakistan Food Security Intelligence Engine.
/// Connects to /api/v1/chat/run-agent for interactive agricultural intelligence queries.
class ChatScreen extends StatefulWidget {
  const ChatScreen({super.key});

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> with TickerProviderStateMixin {
  final TextEditingController _controller = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  final List<_ChatMessage> _messages = [];
  bool _isLoading = false;

  // Suggested queries for quick access
  static const List<String> _suggestions = [
    'What is the wheat price trend in Punjab?',
    'Is there a flood risk in Sindh this week?',
    'Compare food prices across major cities',
    'What disasters are currently affecting Pakistan?',
    'Simulate wheat subsidy impact on prices',
  ];

  @override
  void dispose() {
    _controller.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  void _scrollToBottom() {
    Future.delayed(const Duration(milliseconds: 150), () {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 350),
          curve: Curves.easeOutCubic,
        );
      }
    });
  }

  Future<void> _sendMessage(String text) async {
    if (text.trim().isEmpty) return;

    setState(() {
      _messages.add(_ChatMessage(text: text.trim(), isUser: true));
      _isLoading = true;
      _controller.clear();
    });
    _scrollToBottom();

    try {
      final response = await http
          .post(
            Uri.parse('${ApiConfig.baseUrl}/chat/run-agent'),
            headers: {'Content-Type': 'application/json'},
            body: json.encode({
              'user_query': text.trim(),
              'refresh': false,
              'use_openai': true,
            }),
          )
          .timeout(const Duration(seconds: 120));

      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        final agentResponse = _parseAgentResponse(data);

        if (mounted) {
          setState(() {
            _messages.add(_ChatMessage(
              text: agentResponse.summary,
              isUser: false,
              signals: agentResponse.signals,
              actions: agentResponse.actions,
              sources: agentResponse.sources,
              riskScore: agentResponse.riskScore,
            ));
            _isLoading = false;
          });
          _scrollToBottom();
        }
      } else {
        _addErrorMessage('Server error: ${response.statusCode}');
      }
    } catch (e) {
      _addErrorMessage('Could not connect to the intelligence engine.');
    }
  }

  _AgentResponse _parseAgentResponse(Map<String, dynamic> data) {
    // Extract the main answer
    String summary = '';
    List<String> signals = [];
    List<String> actions = [];
    List<String> sources = [];
    double riskScore = 0.0;

    // Parse the answer field (from OpenAI agent)
    if (data.containsKey('final_reasoning') && data['final_reasoning'] != null) {
      summary = data['final_reasoning'].toString();
    } else if (data.containsKey('answer') && data['answer'] != null) {
      summary = data['answer'].toString();
    }


    // Parse signals
    final rawSignals = data['signals'] as List<dynamic>? ?? [];
    for (var sig in rawSignals) {
      if (sig is Map) {
        final region = sig['region'] ?? '';
        final score = sig['composite_risk_score'] ?? sig['score'] ?? 0;
        final level = sig['risk_level'] ?? sig['level'] ?? '';
        signals.add('$region — Risk: $score ($level)');

        // Use the first signal's score as overall risk
        if (riskScore == 0.0 && score is num) {
          riskScore = score.toDouble();
        }
      }
    }

    // Parse action chain
    final rawActions = data['action_chain'] as List<dynamic>? ?? [];
    for (var act in rawActions) {
      if (act is Map) {
        actions.add(act['title'] ?? act['action'] ?? act.toString());
      } else {
        actions.add(act.toString());
      }
    }

    // Parse sources from reasoning trace
    final rawTrace = data['reasoning_trace'] as List<dynamic>? ?? [];
    for (var trace in rawTrace) {
      if (trace.toString().contains('source') || trace.toString().contains('http')) {
        sources.add(trace.toString());
      }
    }

    // Fallback: if no answer but we have signals, create a summary
    if (summary.isEmpty && signals.isNotEmpty) {
      summary = 'Analysis complete. Found ${signals.length} risk signal(s) '
          'and ${actions.length} recommended action(s).';
    } else if (summary.isEmpty) {
      summary = 'Analysis complete. No immediate risks detected for the specified region.';
    }

    return _AgentResponse(
      summary: summary,
      signals: signals,
      actions: actions,
      sources: sources,
      riskScore: riskScore.clamp(0.0, 100.0),
    );
  }

  void _addErrorMessage(String msg) {
    if (mounted) {
      setState(() {
        _messages.add(_ChatMessage(text: '⚠️ $msg', isUser: false, isError: true));
        _isLoading = false;
      });
      _scrollToBottom();
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0A0E17),
      body: SafeArea(
        child: Column(
          children: [
            _buildHeader(),
            Expanded(
              child: _messages.isEmpty ? _buildEmptyState() : _buildMessageList(),
            ),
            if (_isLoading) _buildTypingIndicator(),
            _buildInputBar(),
          ],
        ),
      ),
    );
  }

  // ── Header ────────────────────────────────────────────────────────────────

  Widget _buildHeader() {
    return Container(
      padding: const EdgeInsets.fromLTRB(24, 16, 24, 12),
      decoration: BoxDecoration(
        border: Border(
          bottom: BorderSide(
            color: const Color(0xFF00FFA3).withOpacity(0.15),
            width: 1,
          ),
        ),
      ),
      child: Row(
        children: [
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(12),
              gradient: const LinearGradient(
                colors: [Color(0xFF00FFA3), Color(0xFF00D68F)],
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
              ),
              boxShadow: [
                BoxShadow(
                  color: const Color(0xFF00FFA3).withOpacity(0.3),
                  blurRadius: 12,
                  offset: const Offset(0, 4),
                ),
              ],
            ),
            child: const Icon(Icons.psychology, color: Color(0xFF0A0E17), size: 22),
          ).animate().scale(duration: 400.ms, curve: Curves.elasticOut),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Intelligence Agent',
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: 17,
                    fontWeight: FontWeight.w600,
                    letterSpacing: -0.3,
                  ),
                ),
                Text(
                  'Food Security • Climate • Market Analysis',
                  style: TextStyle(
                    color: Colors.white.withOpacity(0.4),
                    fontSize: 11,
                    letterSpacing: 0.5,
                  ),
                ),
              ],
            ),
          ),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
            decoration: BoxDecoration(
              color: const Color(0xFF00FFA3).withOpacity(0.12),
              borderRadius: BorderRadius.circular(8),
              border: Border.all(
                color: const Color(0xFF00FFA3).withOpacity(0.3),
              ),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Container(
                  width: 6,
                  height: 6,
                  decoration: const BoxDecoration(
                    color: Color(0xFF00FFA3),
                    shape: BoxShape.circle,
                  ),
                ),
                const SizedBox(width: 6),
                const Text(
                  'LIVE',
                  style: TextStyle(
                    color: Color(0xFF00FFA3),
                    fontSize: 10,
                    fontWeight: FontWeight.bold,
                    letterSpacing: 1.5,
                  ),
                ),
              ],
            ),
          ).animate(onPlay: (c) => c.repeat(reverse: true))
              .fade(begin: 0.7, end: 1.0, duration: 1500.ms),
        ],
      ),
    ).animate().fade(duration: 300.ms).slideY(begin: -0.15);
  }

  // ── Empty State with Suggestions ──────────────────────────────────────────

  Widget _buildEmptyState() {
    return SingleChildScrollView(
      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 32),
      child: Column(
        children: [
          const SizedBox(height: 20),
          Container(
            width: 72,
            height: 72,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              gradient: LinearGradient(
                colors: [
                  const Color(0xFF00FFA3).withOpacity(0.15),
                  const Color(0xFFFFD700).withOpacity(0.08),
                ],
              ),
              border: Border.all(
                color: const Color(0xFF00FFA3).withOpacity(0.25),
                width: 1.5,
              ),
            ),
            child: Icon(
              Icons.auto_awesome,
              color: const Color(0xFF00FFA3).withOpacity(0.8),
              size: 32,
            ),
          ).animate().scale(delay: 200.ms, duration: 500.ms, curve: Curves.elasticOut),
          const SizedBox(height: 20),
          Text(
            'Ask About Pakistan\'s\nFood Security',
            textAlign: TextAlign.center,
            style: TextStyle(
              color: Colors.white.withOpacity(0.85),
              fontSize: 22,
              fontWeight: FontWeight.w600,
              height: 1.3,
            ),
          ).animate().fade(delay: 300.ms).slideY(begin: 0.15),
          const SizedBox(height: 10),
          Text(
            'Powered by real-time market data, weather intelligence,\nand multi-source risk analysis.',
            textAlign: TextAlign.center,
            style: TextStyle(
              color: Colors.white.withOpacity(0.35),
              fontSize: 13,
              height: 1.5,
            ),
          ).animate().fade(delay: 400.ms),
          const SizedBox(height: 32),
          ..._suggestions.asMap().entries.map((entry) {
            final delayMs = 500 + (entry.key * 80);
            return Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: _buildSuggestionChip(entry.value),
            ).animate().fade(delay: Duration(milliseconds: delayMs)).slideX(begin: 0.1);
          }),
        ],
      ),
    );
  }

  Widget _buildSuggestionChip(String text) {
    return GestureDetector(
      onTap: () => _sendMessage(text),
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        decoration: BoxDecoration(
          color: const Color(0xFF121A2E).withOpacity(0.7),
          borderRadius: BorderRadius.circular(14),
          border: Border.all(
            color: Colors.white.withOpacity(0.08),
            width: 1,
          ),
        ),
        child: Row(
          children: [
            Icon(
              Icons.arrow_forward_ios_rounded,
              color: const Color(0xFF00FFA3).withOpacity(0.5),
              size: 14,
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Text(
                text,
                style: TextStyle(
                  color: Colors.white.withOpacity(0.65),
                  fontSize: 13.5,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  // ── Message List ──────────────────────────────────────────────────────────

  Widget _buildMessageList() {
    return ListView.builder(
      controller: _scrollController,
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
      itemCount: _messages.length,
      itemBuilder: (context, index) {
        final msg = _messages[index];
        return Padding(
          padding: const EdgeInsets.only(bottom: 16),
          child: msg.isUser ? _buildUserBubble(msg) : _buildAgentBubble(msg),
        ).animate().fade(duration: 250.ms).slideY(begin: 0.08);
      },
    );
  }

  Widget _buildUserBubble(_ChatMessage msg) {
    return Align(
      alignment: Alignment.centerRight,
      child: Container(
        constraints: BoxConstraints(
          maxWidth: MediaQuery.of(context).size.width * 0.78,
        ),
        padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 13),
        decoration: BoxDecoration(
          borderRadius: const BorderRadius.only(
            topLeft: Radius.circular(20),
            topRight: Radius.circular(20),
            bottomLeft: Radius.circular(20),
            bottomRight: Radius.circular(6),
          ),
          gradient: const LinearGradient(
            colors: [Color(0xFF00FFA3), Color(0xFF00D68F)],
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
          ),
          boxShadow: [
            BoxShadow(
              color: const Color(0xFF00FFA3).withOpacity(0.2),
              blurRadius: 12,
              offset: const Offset(0, 4),
            ),
          ],
        ),
        child: Text(
          msg.text,
          style: const TextStyle(
            color: Color(0xFF0A0E17),
            fontSize: 14.5,
            fontWeight: FontWeight.w500,
            height: 1.4,
          ),
        ),
      ),
    );
  }

  Widget _buildAgentBubble(_ChatMessage msg) {
    return Align(
      alignment: Alignment.centerLeft,
      child: Container(
        constraints: BoxConstraints(
          maxWidth: MediaQuery.of(context).size.width * 0.88,
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Agent label
            Padding(
              padding: const EdgeInsets.only(left: 4, bottom: 6),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Container(
                    width: 20,
                    height: 20,
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(6),
                      color: const Color(0xFF00FFA3).withOpacity(0.15),
                    ),
                    child: const Icon(
                      Icons.psychology,
                      color: Color(0xFF00FFA3),
                      size: 13,
                    ),
                  ),
                  const SizedBox(width: 6),
                  Text(
                    'Intelligence Agent',
                    style: TextStyle(
                      color: Colors.white.withOpacity(0.35),
                      fontSize: 11,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                ],
              ),
            ),
            // Main response bubble
            ClipRRect(
              borderRadius: BorderRadius.circular(18),
              child: BackdropFilter(
                filter: ui.ImageFilter.blur(sigmaX: 10, sigmaY: 10),
                child: Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(18),
                    color: msg.isError
                        ? Colors.red.withOpacity(0.08)
                        : const Color(0xFF121A2E).withOpacity(0.85),
                    border: Border.all(
                      color: msg.isError
                          ? Colors.red.withOpacity(0.25)
                          : Colors.white.withOpacity(0.08),
                      width: 1,
                    ),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      // Risk score badge (if present)
                      if (msg.riskScore != null && msg.riskScore! > 0)
                        Padding(
                          padding: const EdgeInsets.only(bottom: 12),
                          child: _buildRiskBadge(msg.riskScore!),
                        ),
                      // Main text parsed for basic markdown
                      Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: msg.text.split('\n').map((line) {
                          final trimmedLine = line.trim();
                          if (trimmedLine.startsWith('#')) {
                            // Find the header level by counting leading '#'
                            int level = 0;
                            while (level < trimmedLine.length && trimmedLine[level] == '#') {
                              level++;
                            }
                            
                            // Strip leading '#' symbols and space
                            String headerText = trimmedLine.substring(level).trim();
                            
                            // Define beautiful, hierarchical typography for headers
                            double fontSize;
                            Color color;
                            switch (level) {
                              case 1:
                                fontSize = 20;
                                color = Colors.white;
                                break;
                              case 2:
                                fontSize = 18;
                                color = const Color(0xFF00FFA3);
                                break;
                              case 3:
                                fontSize = 16;
                                color = Colors.white;
                                break;
                              default:
                                fontSize = 14;
                                color = Colors.white70;
                            }
                            
                            return Padding(
                              padding: EdgeInsets.only(
                                top: level == 1 ? 20.0 : 14.0,
                                bottom: 8.0,
                              ),
                              child: _buildRichText(
                                context,
                                headerText,
                                TextStyle(
                                  color: color,
                                  fontSize: fontSize,
                                  fontWeight: FontWeight.bold,
                                  height: 1.3,
                                ),
                              ),
                            );
                          } else if (trimmedLine.startsWith('- ') || trimmedLine.startsWith('* ')) {
                            final bulletText = trimmedLine.replaceFirst(RegExp(r'^[-*]\s*'), '');
                            return Padding(
                              padding: const EdgeInsets.only(left: 8.0, bottom: 4.0),
                              child: Row(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  const Text(
                                    '• ',
                                    style: TextStyle(
                                      color: Color(0xFF00FFA3),
                                      fontSize: 14,
                                      height: 1.55,
                                    ),
                                  ),
                                  Expanded(
                                    child: _buildRichText(
                                      context,
                                      bulletText,
                                      TextStyle(
                                        color: msg.isError ? Colors.red[200] : Colors.white.withOpacity(0.85),
                                        fontSize: 14,
                                        height: 1.55,
                                      ),
                                    ),
                                  ),
                                ],
                              ),
                            );
                          } else if (trimmedLine.isNotEmpty) {
                            return Padding(
                              padding: const EdgeInsets.only(bottom: 8.0),
                              child: _buildRichText(
                                context,
                                trimmedLine,
                                TextStyle(
                                  color: msg.isError ? Colors.red[200] : Colors.white.withOpacity(0.85),
                                  fontSize: 14,
                                  height: 1.55,
                                ),
                              ),
                            );
                          } else {
                            return const SizedBox(height: 4);
                          }
                        }).toList(),
                      ),
                      // Signals section
                      if (msg.signals != null && msg.signals!.isNotEmpty) ...[
                        const SizedBox(height: 14),
                        _buildExpandableSection(
                          'Risk Signals',
                          Icons.warning_amber_rounded,
                          const Color(0xFFFFD700),
                          msg.signals!,
                        ),
                      ],
                      // Actions section
                      if (msg.actions != null && msg.actions!.isNotEmpty) ...[
                        const SizedBox(height: 10),
                        _buildExpandableSection(
                          'Recommended Actions',
                          Icons.task_alt,
                          const Color(0xFF00FFA3),
                          msg.actions!,
                        ),
                      ],
                    ],
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildRichText(BuildContext context, String text, TextStyle baseStyle) {
    final List<InlineSpan> spans = [];
    
    // Explicitly merge with theme's bodyMedium (Outfit) to guarantee font family and weights
    final themeStyle = Theme.of(context).textTheme.bodyMedium ?? const TextStyle();
    final mergedStyle = themeStyle.merge(baseStyle);
    
    final parts = text.split('**');
    
    for (int i = 0; i < parts.length; i++) {
      if (parts[i].isEmpty && i == 0) continue;
      final isBold = i % 2 == 1;
      spans.add(
        TextSpan(
          text: parts[i],
          style: mergedStyle.copyWith(
            fontWeight: isBold ? FontWeight.bold : mergedStyle.fontWeight,
            color: isBold ? const Color(0xFF00FFA3) : mergedStyle.color,
          ),
        ),
      );
    }
    
    return Text.rich(
      TextSpan(
        children: spans,
        style: mergedStyle,
      ),
    );
  }

  Widget _buildRiskBadge(double score) {
    Color badgeColor;
    String label;
    if (score >= 70) {
      badgeColor = const Color(0xFFFF4757);
      label = 'HIGH RISK';
    } else if (score >= 40) {
      badgeColor = const Color(0xFFFFD700);
      label = 'MODERATE RISK';
    } else {
      badgeColor = const Color(0xFF00FFA3);
      label = 'LOW RISK';
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
        color: badgeColor.withOpacity(0.12),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: badgeColor.withOpacity(0.35)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 8,
            height: 8,
            decoration: BoxDecoration(
              color: badgeColor,
              shape: BoxShape.circle,
              boxShadow: [
                BoxShadow(color: badgeColor, blurRadius: 6, spreadRadius: 1),
              ],
            ),
          ),
          const SizedBox(width: 8),
          Text(
            '$label • ${score.toStringAsFixed(0)}',
            style: TextStyle(
              color: badgeColor,
              fontSize: 11,
              fontWeight: FontWeight.bold,
              letterSpacing: 0.8,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildExpandableSection(
    String title,
    IconData icon,
    Color color,
    List<String> items,
  ) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: color.withOpacity(0.06),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withOpacity(0.15)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(icon, color: color, size: 16),
              const SizedBox(width: 8),
              Text(
                title,
                style: TextStyle(
                  color: color,
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                  letterSpacing: 0.5,
                ),
              ),
              const SizedBox(width: 6),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                decoration: BoxDecoration(
                  color: color.withOpacity(0.15),
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Text(
                  '${items.length}',
                  style: TextStyle(color: color, fontSize: 10, fontWeight: FontWeight.bold),
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          ...items.take(5).map((item) => Padding(
                padding: const EdgeInsets.only(bottom: 4),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('  •  ', style: TextStyle(color: color.withOpacity(0.5), fontSize: 12)),
                    Expanded(
                      child: Text(
                        item,
                        style: TextStyle(
                          color: Colors.white.withOpacity(0.6),
                          fontSize: 12,
                          height: 1.4,
                        ),
                      ),
                    ),
                  ],
                ),
              )),
          if (items.length > 5)
            Padding(
              padding: const EdgeInsets.only(top: 4),
              child: Text(
                '  +${items.length - 5} more…',
                style: TextStyle(
                  color: color.withOpacity(0.5),
                  fontSize: 11,
                  fontStyle: FontStyle.italic,
                ),
              ),
            ),
        ],
      ),
    );
  }

  // ── Typing Indicator ──────────────────────────────────────────────────────

  Widget _buildTypingIndicator() {
    return Align(
      alignment: Alignment.centerLeft,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(20, 0, 20, 8),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              decoration: BoxDecoration(
                color: const Color(0xFF121A2E).withOpacity(0.85),
                borderRadius: BorderRadius.circular(16),
                border: Border.all(
                  color: const Color(0xFF00FFA3).withOpacity(0.15),
                ),
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  _buildDot(0),
                  const SizedBox(width: 5),
                  _buildDot(200),
                  const SizedBox(width: 5),
                  _buildDot(400),
                  const SizedBox(width: 10),
                  Text(
                    'Analyzing...',
                    style: TextStyle(
                      color: Colors.white.withOpacity(0.35),
                      fontSize: 12,
                      fontStyle: FontStyle.italic,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    ).animate().fade(duration: 200.ms);
  }

  Widget _buildDot(int delayMs) {
    return Container(
      width: 7,
      height: 7,
      decoration: BoxDecoration(
        color: const Color(0xFF00FFA3).withOpacity(0.6),
        shape: BoxShape.circle,
      ),
    )
        .animate(onPlay: (controller) => controller.repeat(reverse: true))
        .fade(begin: 0.3, end: 1.0, delay: Duration(milliseconds: delayMs), duration: 500.ms)
        .scale(begin: const Offset(0.7, 0.7), end: const Offset(1.0, 1.0), delay: Duration(milliseconds: delayMs), duration: 500.ms);
  }

  // ── Input Bar ─────────────────────────────────────────────────────────────

  Widget _buildInputBar() {
    return Container(
      padding: const EdgeInsets.fromLTRB(12, 10, 12, 12),
      decoration: BoxDecoration(
        color: const Color(0xFF0A0E17),
        border: Border(
          top: BorderSide(
            color: Colors.white.withOpacity(0.08),
            width: 1,
          ),
        ),
      ),
      child: SafeArea(
        top: false,
        child: Row(
          children: [
            Expanded(
              child: Container(
                decoration: BoxDecoration(
                  color: const Color(0xFF121A2E),
                  borderRadius: BorderRadius.circular(24),
                  border: Border.all(
                    color: Colors.white.withOpacity(0.08),
                  ),
                ),
                child: TextField(
                  controller: _controller,
                  enabled: !_isLoading,
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 14,
                  ),
                  maxLines: 3,
                  minLines: 1,
                  decoration: InputDecoration(
                    hintText: 'Ask about food security, prices, weather...',
                    hintStyle: TextStyle(
                      color: Colors.white.withOpacity(0.25),
                      fontSize: 14,
                    ),
                    border: InputBorder.none,
                    contentPadding: const EdgeInsets.symmetric(
                      horizontal: 18,
                      vertical: 12,
                    ),
                  ),
                  onSubmitted: _isLoading ? null : _sendMessage,
                  textInputAction: TextInputAction.send,
                ),
              ),
            ),
            const SizedBox(width: 10),
            GestureDetector(
              onTap: _isLoading ? null : () => _sendMessage(_controller.text),
              child: AnimatedContainer(
                duration: const Duration(milliseconds: 200),
                width: 46,
                height: 46,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  gradient: _isLoading
                      ? LinearGradient(
                          colors: [
                            Colors.white.withOpacity(0.1),
                            Colors.white.withOpacity(0.05),
                          ],
                        )
                      : const LinearGradient(
                          colors: [Color(0xFF00FFA3), Color(0xFF00D68F)],
                          begin: Alignment.topLeft,
                          end: Alignment.bottomRight,
                        ),
                  boxShadow: _isLoading
                      ? []
                      : [
                          BoxShadow(
                            color: const Color(0xFF00FFA3).withOpacity(0.3),
                            blurRadius: 12,
                            offset: const Offset(0, 4),
                          ),
                        ],
                ),
                child: Icon(
                  _isLoading ? Icons.hourglass_top_rounded : Icons.arrow_upward_rounded,
                  color: _isLoading ? Colors.white38 : const Color(0xFF0A0E17),
                  size: 22,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// ── Data Models ───────────────────────────────────────────────────────────────

class _ChatMessage {
  final String text;
  final bool isUser;
  final bool isError;
  final List<String>? signals;
  final List<String>? actions;
  final List<String>? sources;
  final double? riskScore;

  const _ChatMessage({
    required this.text,
    required this.isUser,
    this.isError = false,
    this.signals,
    this.actions,
    this.sources,
    this.riskScore,
  });
}

class _AgentResponse {
  final String summary;
  final List<String> signals;
  final List<String> actions;
  final List<String> sources;
  final double riskScore;

  const _AgentResponse({
    required this.summary,
    required this.signals,
    required this.actions,
    required this.sources,
    required this.riskScore,
  });
}
