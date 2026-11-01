/* =========================================================
   NEWS SERVICE - Backend-ready architecture
   
   This service provides a clean abstraction for news data.
   Currently returns mock data, but can be easily replaced
   with API calls to a real backend.
   
   TODO: Replace with actual API calls
   - GET /api/news/global
   - GET /api/news/india
   - GET /api/news/recommended
   - GET /api/news/for-you
   - GET /api/news/trending
   
   ========================================================= */

import {
  globalNews,
  indiaNews,
  recommendedNews,
  forYouNews,
  categories,
  popularTopics,
} from "../data/newsData";

// Simulate network delay for realistic behavior
const simulateDelay = (ms = 300) =>
  new Promise((resolve) => setTimeout(resolve, ms));

const shuffleNews = (news) => {
  const shuffled = [...news];

  for (let index = shuffled.length - 1; index > 0; index -= 1) {
    const swapIndex = Math.floor(Math.random() * (index + 1));
    [shuffled[index], shuffled[swapIndex]] = [
      shuffled[swapIndex],
      shuffled[index],
    ];
  }

  return shuffled;
};

export const newsService = {
  /**
   * Get global news articles
   * TODO: Replace with GET /api/news/global
   */
  async getGlobalNews() {
    await simulateDelay(300);
    return globalNews;
  },

  /**
   * Get India-specific news articles
   * TODO: Replace with GET /api/news/india
   */
  async getIndiaNews() {
    await simulateDelay(300);
    return indiaNews;
  },

  /**
   * Get recommended news for user
   * TODO: Replace with GET /api/news/recommended
   */
  async getRecommendedNews() {
    await simulateDelay(300);
    return recommendedNews;
  },

  /**
   * Get personalized "For You" news
   * TODO: Replace with GET /api/news/for-you
   */
  async getForYouNews() {
    await simulateDelay(300);
    return forYouNews;
  },

  /**
   * Get trending news combined from all sources
   * TODO: Replace with GET /api/news/trending
   */
  async getTrendingNews() {
    await simulateDelay(300);
    // Combine all news and sort by reads/recency
    const allNews = [
      ...globalNews,
      ...indiaNews,
      ...recommendedNews,
      ...forYouNews,
    ];
    return shuffleNews(allNews).slice(0, 20);
  },

  /**
   * Filter news by category and region
   * TODO: Replace with GET /api/news/filter?category=X&region=Y
   */
  async filterNews(region, category) {
    await simulateDelay(300);
    let news = [];

    if (region === "Global") {
      news = globalNews;
    } else if (region === "India") {
      news = indiaNews;
    } else if (region === "For You") {
      news = forYouNews;
    }

    if (category && category !== "All Categories") {
      news = news.filter(
        (item) => item.category === category
      );
    }

    return news;
  },

  /**
   * Search news by topic/keyword
   * TODO: Replace with GET /api/news/search?q=keyword
   */
  async searchNews(keyword) {
    await simulateDelay(300);
    const allNews = [
      ...globalNews,
      ...indiaNews,
      ...recommendedNews,
      ...forYouNews,
    ];

    return allNews.filter(
      (item) =>
        item.title
          .toLowerCase()
          .includes(keyword.toLowerCase()) ||
        item.description
          .toLowerCase()
          .includes(keyword.toLowerCase()) ||
        item.category
          .toLowerCase()
          .includes(keyword.toLowerCase())
    );
  },

  /**
   * Get article details by ID
   * TODO: Replace with GET /api/news/:id
   */
  async getArticleById(id) {
    await simulateDelay(300);
    const allNews = [
      ...globalNews,
      ...indiaNews,
      ...recommendedNews,
      ...forYouNews,
    ];

    return allNews.find((item) => item.id === id);
  },

  /**
   * Get available categories
   */
  getCategories() {
    return categories;
  },

  /**
   * Get popular topics/hashtags
   */
  getPopularTopics() {
    return popularTopics;
  },

  /**
   * Refresh/reshuffle trending news
   * TODO: Replace with POST /api/news/refresh
   */
  async refreshNews() {
    await simulateDelay(500);
    const allNews = [
      ...globalNews,
      ...indiaNews,
      ...recommendedNews,
      ...forYouNews,
    ];
    return shuffleNews(allNews);
  },
};

export default newsService;
