import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:google_fonts/google_fonts.dart';
import '../main.dart';
import 'dart:ui' as ui;

class OnboardingScreen extends StatefulWidget {
  const OnboardingScreen({super.key});

  @override
  State<OnboardingScreen> createState() => _OnboardingScreenState();
}

class _OnboardingScreenState extends State<OnboardingScreen> {
  final PageController _pageController = PageController();
  int _currentPage = 0;

  final List<OnboardingData> _pages = [
    OnboardingData(
      title: 'Autonomous Scraper',
      subtitle: 'Live Data Ingestion',
      description: 'FaslBot autonomously scrapes the Pakistan Bureau of Statistics (PBS) and World Food Programme (WFP) every week to track price volatility.',
      icon: Icons.travel_explore_rounded,
      color: const Color(0xFF00FFA3),
    ),
    OnboardingData(
      title: 'AI Intelligence',
      subtitle: 'Gemini-Powered Analysis',
      description: 'Using Gemini 1.5 Flash, the agent identifies inter-city price arbitrage and potential supply disruptions before they become crises.',
      icon: Icons.psychology_outlined,
      color: const Color(0xFFFFD700),
    ),
    OnboardingData(
      title: 'Strategic Planning',
      subtitle: 'Multi-Agent Orchestration',
      description: 'Our Impact Analyst and Action Planner agents design targeted interventions to stabilize local mandi prices.',
      icon: Icons.analytics_outlined,
      color: const Color(0xFF4FC3F7),
    ),
    OnboardingData(
      title: 'Direct Action',
      subtitle: 'Automated SMS Alerts',
      description: 'FaslBot executes real-time SMS blasts in Urdu to farmers and traders, providing actionable market intelligence to bridge the gap.',
      icon: Icons.sms_failed_outlined,
      color: const Color(0xFFFF6B6B),
    ),
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0A0E17),
      body: Stack(
        children: [
          // Background Glow
          Positioned(
            top: -100,
            right: -100,
            child: Container(
              width: 300,
              height: 300,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: _pages[_currentPage].color.withOpacity(0.1),
              ),
            ),
          ).animate(target: _currentPage.toDouble()).fadeIn(),

          PageView.builder(
            controller: _pageController,
            onPageChanged: (int page) {
              setState(() => _currentPage = page);
            },
            itemCount: _pages.length,
            itemBuilder: (context, index) {
              return _buildPage(_pages[index]);
            },
          ),

          // Bottom Controls
          Positioned(
            bottom: 60,
            left: 24,
            right: 24,
            child: Column(
              children: [
                // Page Indicator
                Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: List.generate(
                    _pages.length,
                    (index) => AnimatedContainer(
                      duration: const Duration(milliseconds: 300),
                      margin: const EdgeInsets.symmetric(horizontal: 4),
                      height: 8,
                      width: _currentPage == index ? 24 : 8,
                      decoration: BoxDecoration(
                        color: _currentPage == index 
                            ? _pages[_currentPage].color 
                            : Colors.white24,
                        borderRadius: BorderRadius.circular(4),
                      ),
                    ),
                  ),
                ),
                const SizedBox(height: 40),
                
                // Get Started / Next Button
                GestureDetector(
                  onTap: () {
                    if (_currentPage == _pages.length - 1) {
                      Navigator.of(context).pushReplacement(
                        MaterialPageRoute(builder: (_) => const MainScreen()),
                      );
                    } else {
                      _pageController.nextPage(
                        duration: const Duration(milliseconds: 500),
                        curve: Curves.easeInOut,
                      );
                    }
                  },
                  child: ClipRRect(
                    borderRadius: BorderRadius.circular(16),
                    child: BackdropFilter(
                      filter: ui.ImageFilter.blur(sigmaX: 10, sigmaY: 10),
                      child: Container(
                        height: 60,
                        width: double.infinity,
                        decoration: BoxDecoration(
                          color: _pages[_currentPage].color.withOpacity(0.15),
                          borderRadius: BorderRadius.circular(16),
                          border: Border.all(
                            color: _pages[_currentPage].color.withOpacity(0.3),
                            width: 1,
                          ),
                        ),
                        child: Center(
                          child: Text(
                            _currentPage == _pages.length - 1 ? 'GET STARTED' : 'NEXT',
                            style: TextStyle(
                              color: _pages[_currentPage].color,
                              fontSize: 16,
                              fontWeight: FontWeight.bold,
                              letterSpacing: 1.5,
                            ),
                          ),
                        ),
                      ),
                    ),
                  ),
                ).animate(key: ValueKey(_currentPage))
                  .fade(duration: 400.ms)
                  .scale(begin: const Offset(0.9, 0.9)),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildPage(OnboardingData data) {
    return Padding(
      padding: const EdgeInsets.all(40),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Container(
            padding: const EdgeInsets.all(30),
            decoration: BoxDecoration(
              color: data.color.withOpacity(0.1),
              shape: BoxShape.circle,
              border: Border.all(color: data.color.withOpacity(0.2), width: 2),
            ),
            child: Icon(
              data.icon,
              size: 80,
              color: data.color,
            ),
          ).animate().scale(duration: 600.ms, curve: Curves.easeOutBack).rotate(begin: -0.1, end: 0),
          const SizedBox(height: 60),
          Text(
            data.subtitle.toUpperCase(),
            style: GoogleFonts.outfit(
              color: data.color,
              fontSize: 14,
              fontWeight: FontWeight.bold,
              letterSpacing: 3,
            ),
          ).animate().fade(delay: 200.ms).slideY(begin: 0.5),
          const SizedBox(height: 12),
          Text(
            data.title,
            textAlign: TextAlign.center,
            style: GoogleFonts.outfit(
              color: Colors.white,
              fontSize: 32,
              fontWeight: FontWeight.bold,
            ),
          ).animate().fade(delay: 300.ms).slideY(begin: 0.5),
          const SizedBox(height: 24),
          Text(
            data.description,
            textAlign: TextAlign.center,
            style: GoogleFonts.outfit(
              color: Colors.white60,
              fontSize: 16,
              height: 1.6,
            ),
          ).animate().fade(delay: 400.ms).slideY(begin: 0.5),
        ],
      ),
    );
  }
}

class OnboardingData {
  final String title;
  final String subtitle;
  final String description;
  final IconData icon;
  final Color color;

  OnboardingData({
    required this.title,
    required this.subtitle,
    required this.description,
    required this.icon,
    required this.color,
  });
}
