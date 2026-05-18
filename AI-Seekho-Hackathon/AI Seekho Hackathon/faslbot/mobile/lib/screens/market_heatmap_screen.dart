import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'dart:ui' as ui;
import 'dart:convert';
import 'package:http/http.dart' as http;
import '../config/api_config.dart';

class MarketHeatmapScreen extends StatefulWidget {
  const MarketHeatmapScreen({super.key});

  @override
  State<MarketHeatmapScreen> createState() => _MarketHeatmapScreenState();
}

class _MarketHeatmapScreenState extends State<MarketHeatmapScreen> {
  List<Map<String, dynamic>> _prices = [];
  bool _isLoading = true;
  String? _error;

  final List<String> _cities = ['Karachi', 'Lahore', 'Islamabad', 'Peshawar', 'Multan'];
  final List<String> _commodities = ['wheat', 'tomato'];

  @override
  void initState() {
    super.initState();
    _fetchPrices();
  }

  Future<void> _fetchPrices() async {
    try {
      final response = await http.get(
        Uri.parse('${ApiConfig.baseUrl}/prices'),
      ).timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        if (mounted) {
          setState(() {
            _prices = List<Map<String, dynamic>>.from(data['data']['prices'] ?? []);
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
          _error = 'Server Connection Error';
          _isLoading = false;
        });
      }
    }
  }

  Map<String, dynamic> _getCityPrices(String city) {
    Map<String, dynamic> result = {
      'wheat': {'price': 0.0, 'unit': 'kg'},
      'tomato': {'price': 0.0, 'unit': 'kg'},
    };

    for (var price in _prices) {
      String priceCity = (price['city'] ?? '').toString().toLowerCase();
      String commodity = (price['commodity'] ?? '').toString().toLowerCase();
      double priceValue = (price['price_pkr'] ?? 0).toDouble();
      String unit = (price['unit'] ?? 'kg').toString();

      if (priceCity.contains(city.toLowerCase())) {
        if (commodity.contains('wheat')) {
          result['wheat'] = {'price': priceValue, 'unit': unit};
        } else if (commodity.contains('tomato')) {
          result['tomato'] = {'price': priceValue, 'unit': unit};
        }
      }
    }
    return result;
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
              child: _buildCommodityLegend(),
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
                        onPressed: _fetchPrices,
                        child: const Text('Retry', style: TextStyle(color: Color(0xFF00FFA3))),
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
                    (context, index) => _buildCityCard(_cities[index], index),
                    childCount: _cities.length,
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
              const Icon(Icons.grid_view_rounded, color: Color(0xFFFFD700), size: 28),
              const SizedBox(width: 12),
              Text(
                'Market Heatmap',
                style: Theme.of(context).textTheme.headlineLarge?.copyWith(
                      color: Colors.white,
                      fontWeight: FontWeight.bold,
                    ),
              ).animate().fade(duration: 600.ms).slideX(begin: -0.2),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            'Live prices across Pakistan',
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
                  const Color(0xFFFFD700).withOpacity(0),
                  const Color(0xFFFFD700).withOpacity(0.5),
                  const Color(0xFF00FFA3).withOpacity(0.3),
                  const Color(0xFF00FFA3).withOpacity(0),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildCommodityLegend() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 8),
      child: Row(
        children: [
          _buildLegendItem('گندم (Wheat)', const Color(0xFFFFD700)),
          const SizedBox(width: 24),
          _buildLegendItem('ٹماٹر (Tomato)', const Color(0xFFFF6B6B)),
        ],
      ),
    );
  }

  Widget _buildLegendItem(String label, Color color) {
    return Row(
      children: [
        Container(
          width: 12,
          height: 12,
          decoration: BoxDecoration(
            color: color,
            borderRadius: BorderRadius.circular(3),
          ),
        ),
        const SizedBox(width: 8),
        Text(label, style: TextStyle(color: Colors.white70, fontSize: 12)),
      ],
    );
  }

  Widget _buildCityCard(String city, int index) {
    final prices = _getCityPrices(city);
    final delayMs = 300 + (index * 100);

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
                          color: const Color(0xFF00FFA3).withOpacity(0.15),
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: const Icon(Icons.location_city, color: Color(0xFF00FFA3), size: 24),
                      ),
                      const SizedBox(width: 12),
                      Text(
                        city,
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 18,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                      const Spacer(),
                      _buildCityBadge(city),
                    ],
                  ),
                  const SizedBox(height: 16),
                  Row(
                    children: [
                      Expanded(
                        child: _buildPriceTile(
                          'گندم',
                          (prices['wheat']?['price'] ?? 0).toDouble(),
                          const Color(0xFFFFD700),
                          prices['wheat']?['unit'] ?? 'kg',
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: _buildPriceTile(
                          'ٹماٹر',
                          (prices['tomato']?['price'] ?? 0).toDouble(),
                          const Color(0xFFFF6B6B),
                          prices['tomato']?['unit'] ?? 'kg',
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

  Widget _buildCityBadge(String city) {
    Color badgeColor;
    IconData badgeIcon;

    switch (city.toLowerCase()) {
      case 'karachi':
        badgeColor = const Color(0xFF4FC3F7);
        badgeIcon = Icons.portrait;
        break;
      case 'lahore':
        badgeColor = const Color(0xFF81C784);
        badgeIcon = Icons.park;
        break;
      case 'islamabad':
        badgeColor = const Color(0xFFBA68C8);
        badgeIcon = Icons.account_balance;
        break;
      case 'peshawar':
        badgeColor = const Color(0xFFFFB74D);
        badgeIcon = Icons.landscape;
        break;
      case 'multan':
        badgeColor = const Color(0xFF4DD0E1);
        badgeIcon = Icons.water_drop;
        break;
      default:
        badgeColor = const Color(0xFF00FFA3);
        badgeIcon = Icons.location_on;
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: badgeColor.withOpacity(0.2),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: badgeColor.withOpacity(0.5)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(badgeIcon, color: badgeColor, size: 14),
          const SizedBox(width: 4),
          Text(
            city.toUpperCase().substring(0, 3),
            style: TextStyle(
              color: badgeColor,
              fontSize: 10,
              fontWeight: FontWeight.bold,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildPriceTile(String label, double price, Color accentColor, [String unit = 'kg']) {
    final hasPrice = price > 0;

    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: accentColor.withOpacity(0.08),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: accentColor.withOpacity(0.3)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            label,
            style: TextStyle(
              color: Colors.white.withOpacity(0.6),
              fontSize: 12,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            hasPrice ? 'PKR ${price.toStringAsFixed(0)}/$unit' : '—',
            style: TextStyle(
              color: accentColor,
              fontSize: 18,
              fontWeight: FontWeight.bold,
            ),
          ),
        ],
      ),
    );
  }
}