import React, { useState, useEffect, useContext } from 'react';
import { View, Text, StyleSheet, ScrollView, Image, TouchableOpacity, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useFocusEffect } from '@react-navigation/native';
import { Ionicons } from '@expo/vector-icons';
import * as Animatable from 'react-native-animatable';
import { AuthContext } from '../context/AuthContext';
import { ThemeContext } from '../context/ThemeContext';
import { API_URL } from '../config/constants';
import Header from '../components/Header';

const BadgesScreen = ({ navigation }) => {
  const [isLoading, setIsLoading] = useState(true);
  const [badges, setBadges] = useState({
    badges: [],
    total_badges: 0,
    badges_by_category: {
      level: [],
      achievement: [],
      special: []
    }
  });
  const [activeCategory, setActiveCategory] = useState('all');
  const { token } = useContext(AuthContext);
  const { theme } = useContext(ThemeContext);

  useFocusEffect(
    React.useCallback(() => {
      fetchBadges();
    }, [])
  );

  const fetchBadges = async () => {
    setIsLoading(true);
    try {
      const response = await fetch(`${API_URL}/api/drivers/badges`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });
      
      const data = await response.json();
      
      if (data.success) {
        setBadges(data);
      }
    } catch (error) {
      console.error('Error fetching badges:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const filterBadges = () => {
    if (activeCategory === 'all') {
      return badges.badges;
    }
    return badges.badges_by_category[activeCategory] || [];
  };

  const renderBadge = (badge, index) => {
    return (
      <Animatable.View 
        animation="fadeIn" 
        delay={index * 100}
        key={badge.id} 
        style={styles.badgeItem}
      >
        <View style={styles.badgeImageContainer}>
          <Image 
            // In a real app, this would be badge.image_url
            source={require('../assets/badge-placeholder.png')}
            style={styles.badgeImage}
            defaultSource={require('../assets/badge-placeholder.png')}
          />
          <View style={[styles.badgeCategoryTag, getCategoryColor(badge.category)]}>
            <Text style={styles.badgeCategoryText}>
              {badge.category.charAt(0).toUpperCase() + badge.category.slice(1)}
            </Text>
          </View>
        </View>
        <Text style={styles.badgeName}>{badge.name}</Text>
        <Text style={styles.badgeDescription}>{badge.description}</Text>
        <Text style={styles.badgeEarnedDate}>Earned {formatDate(badge.earned_at)}</Text>
      </Animatable.View>
    );
  };

  const getCategoryColor = (category) => {
    switch (category) {
      case 'level':
        return { backgroundColor: '#3498db' };
      case 'achievement':
        return { backgroundColor: '#27ae60' };
      case 'special':
        return { backgroundColor: '#9b59b6' };
      default:
        return { backgroundColor: '#95a5a6' };
    }
  };

  const formatDate = (dateString) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  };

  if (isLoading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#3498db" />
        <Text style={styles.loadingText}>Loading badges...</Text>
      </View>
    );
  }

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: theme.backgroundColor }]}>
      <Header title="Your Badges" showBackButton={true} navigation={navigation} />
      
      <View style={styles.statsBanner}>
        <Text style={styles.statValue}>{badges.total_badges}</Text>
        <Text style={styles.statLabel}>Total Badges Earned</Text>
      </View>
      
      <View style={styles.categoryFilter}>
        <ScrollView horizontal showsHorizontalScrollIndicator={false}>
          <TouchableOpacity
            style={[
              styles.categoryButton,
              activeCategory === 'all' ? styles.activeCategoryButton : null
            ]}
            onPress={() => setActiveCategory('all')}
          >
            <Text style={[
              styles.categoryButtonText,
              activeCategory === 'all' ? styles.activeCategoryText : null
            ]}>All</Text>
          </TouchableOpacity>
          
          <TouchableOpacity
            style={[
              styles.categoryButton,
              activeCategory === 'level' ? styles.activeCategoryButton : null
            ]}
            onPress={() => setActiveCategory('level')}
          >
            <Text style={[
              styles.categoryButtonText,
              activeCategory === 'level' ? styles.activeCategoryText : null
            ]}>Level</Text>
          </TouchableOpacity>
          
          <TouchableOpacity
  style={[
    styles.categoryButton,
    activeCategory === 'achievement' ? styles.activeCategoryButton : null
  ]}
  onPress={() => setActiveCategory('achievement')}
>
  <Text style={[
    styles.categoryButtonText,
    activeCategory === 'achievement' ? styles.activeCategoryText : null
  ]}>Achievement</Text>
</TouchableOpacity>

<TouchableOpacity
  style={[
    styles.categoryButton,
    activeCategory === 'special' ? styles.activeCategoryButton : null
  ]}
  onPress={() => setActiveCategory('special')}
>
  <Text style={[
    styles.categoryButtonText,
    activeCategory === 'special' ? styles.activeCategoryText : null
  ]}>Special</Text>
</TouchableOpacity>
</ScrollView>
</View>
        
        {filterBadges().length > 0 ? (
          <ScrollView 
            style={styles.badgesList}
            contentContainerStyle={styles.badgesListContent}
          >
            {filterBadges().map((badge, index) => renderBadge(badge, index))}
          </ScrollView>
        ) : (
          <View style={styles.emptyStateContainer}>
            <Image 
              source={require('../assets/empty-badges.png')}
              style={styles.emptyStateImage}
            />
            <Text style={styles.emptyStateTitle}>No Badges Yet</Text>
            <Text style={styles.emptyStateText}>
              Complete trips and challenges to earn badges and showcase your achievements!
            </Text>
          </View>
        )}
      </SafeAreaView>
    );
  };
  
  const styles = StyleSheet.create({
    container: {
      flex: 1,
    },
    loadingContainer: {
      flex: 1,
      justifyContent: 'center',
      alignItems: 'center',
    },
    loadingText: {
      marginTop: 10,
      fontSize: 16,
      color: '#7f8c8d',
    },
    statsBanner: {
      backgroundColor: '#3498db',
      padding: 15,
      alignItems: 'center',
      marginHorizontal: 16,
      marginTop: 16,
      borderRadius: 12,
      shadowColor: '#000',
      shadowOffset: { width: 0, height: 2 },
      shadowOpacity: 0.1,
      shadowRadius: 4,
      elevation: 2,
    },
    statValue: {
      fontSize: 28,
      fontWeight: 'bold',
      color: '#fff',
    },
    statLabel: {
      fontSize: 14,
      color: '#fff',
      opacity: 0.9,
    },
    categoryFilter: {
      marginTop: 20,
      paddingHorizontal: 16,
    },
    categoryButton: {
      paddingHorizontal: 20,
      paddingVertical: 8,
      borderRadius: 20,
      backgroundColor: '#f1f2f6',
      marginRight: 10,
    },
    activeCategoryButton: {
      backgroundColor: '#3498db',
    },
    categoryButtonText: {
      fontSize: 14,
      color: '#7f8c8d',
    },
    activeCategoryText: {
      color: '#fff',
      fontWeight: '600',
    },
    badgesList: {
      flex: 1,
      marginTop: 20,
    },
    badgesListContent: {
      paddingHorizontal: 16,
      paddingBottom: 20,
    },
    badgeItem: {
      backgroundColor: '#fff',
      borderRadius: 12,
      padding: 16,
      marginBottom: 16,
      shadowColor: '#000',
      shadowOffset: { width: 0, height: 2 },
      shadowOpacity: 0.1,
      shadowRadius: 4,
      elevation: 2,
    },
    badgeImageContainer: {
      position: 'relative',
      alignItems: 'center',
      marginBottom: 12,
    },
    badgeImage: {
      width: 100,
      height: 100,
      borderRadius: 50,
    },
    badgeCategoryTag: {
      position: 'absolute',
      bottom: 0,
      paddingHorizontal: 12,
      paddingVertical: 4,
      borderRadius: 12,
    },
    badgeCategoryText: {
      color: '#fff',
      fontSize: 12,
      fontWeight: '600',
    },
    badgeName: {
      fontSize: 18,
      fontWeight: 'bold',
      textAlign: 'center',
      marginBottom: 8,
      color: '#2c3e50',
    },
    badgeDescription: {
      fontSize: 14,
      textAlign: 'center',
      color: '#7f8c8d',
      marginBottom: 8,
    },
    badgeEarnedDate: {
      fontSize: 12,
      textAlign: 'center',
      color: '#95a5a6',
      fontStyle: 'italic',
    },
    emptyStateContainer: {
      flex: 1,
      justifyContent: 'center',
      alignItems: 'center',
      padding: 20,
    },
    emptyStateImage: {
      width: 120,
      height: 120,
      marginBottom: 20,
      opacity: 0.7,
    },
    emptyStateTitle: {
      fontSize: 20,
      fontWeight: 'bold',
      color: '#2c3e50',
      marginBottom: 8,
    },
    emptyStateText: {
      fontSize: 14,
      textAlign: 'center',
      color: '#7f8c8d',
      lineHeight: 20,
      maxWidth: '80%',
    }
  });
  
  export default BadgesScreen;