# Quick Testing Checklist - Trending News

## ✅ Functional Features Quick Test

### 1. Navigation & Tabs
- [ ] Click "For You" tab - shows personalized news
- [ ] Click "Global" tab - shows global news  
- [ ] Click "India" tab - shows India-specific news
- [ ] Tab highlight shows active state

### 2. Category Filter
- [ ] Select "Technology" - filters correctly
- [ ] Select "Business" - filters correctly
- [ ] Select "All Categories" - shows all
- [ ] Filter works independently in each tab

### 3. Hero Slider
- [ ] Hero article displays at top
- [ ] Click pagination dots - article changes
- [ ] Auto-slide happens every 5 seconds
- [ ] "Read Full Story" button works

### 4. Save & Like
- [ ] Click heart - fills and turns filled (♥)
- [ ] Click save - shows checked (▣)
- [ ] State persists after page refresh
- [ ] Check localStorage: F12 → Application → Local Storage → verifyai_saved_articles
- [ ] Works in article cards AND article reader

### 5. Refresh Button
- [ ] Click refresh - shows loading state
- [ ] News articles reshuffle
- [ ] Button re-enables after refresh

### 6. View All Buttons
- [ ] "Top Trending - Global" → "View All" → shows all global
- [ ] "Top Trending - India" → "View All" → shows all India
- [ ] "Recommended for You" → "View All" → shows recommendations

### 7. Article Reader
- [ ] Click any article card - opens full reader page
- [ ] Shows: image, title, description, content
- [ ] Save button works
- [ ] Like button works
- [ ] "Verify" button opens Analyze page
- [ ] "Back to Trending" button returns to list

### 8. Responsive Testing
**Desktop (1200px+)**
- [ ] See 3-column layout
- [ ] Left sidebar, center content, right recommended

**Tablet (781-1199px)**
- [ ] See 2-column layout
- [ ] Proper stacking

**Mobile (320-780px)**
- [ ] See 1-column layout
- [ ] No horizontal scroll
- [ ] All buttons clickable

### 9. Error Handling
- [ ] Filter returns no results - shows empty state
- [ ] Images fail to load - shows no broken elements
- [ ] All buttons clickable even with no data

### 10. Dark Mode (if available)
- [ ] Toggle dark theme
- [ ] All new components adapt colors
- [ ] Text remains readable
- [ ] Buttons visible and clickable

---

## 🔍 Developer Testing

### Console Check
```javascript
// In browser console:
localStorage.getItem('verifyai_saved_articles')   // Should show array
localStorage.getItem('verifyai_liked_articles')   // Should show array
```

### Service Testing
```javascript
// In browser console:
import newsService from './services/newsService.js'
newsService.getGlobalNews().then(news => console.log(news))
```

### Build Check
```bash
npm run build   # Should complete with no errors
npm run dev     # Should start without errors
```

---

## 📊 Test Data Overview

**Global News**: 12 articles covering Technology, World, Environment, Politics, Business, Health, Sports, Science

**India News**: 10 articles covering India, Business, Politics, Sports, Technology, Health, Environment, Science

**Recommended**: 6 articles with variety of categories

**For You**: 6 articles personalized mix

---

## 🐛 Common Issues & Fixes

### Issue: Articles not showing
- **Fix**: Check if newsService is properly imported
- **Fix**: Check browser console for errors
- **Fix**: Verify mock data structure in newsData.js

### Issue: Save/Like not persisting
- **Fix**: Clear localStorage and try again
- **Fix**: Check if localStorage is enabled
- **Fix**: Verify localStorage keys: `verifyai_saved_articles`, `verifyai_liked_articles`

### Issue: Article reader not opening
- **Fix**: Ensure `setSelectedArticle` state is working
- **Fix**: Check console for errors
- **Fix**: Verify article data structure has all required fields

### Issue: Images not loading
- **Fix**: Check if URLs are accessible
- **Fix**: Network tab shows 404 - use fallback handling
- **Fix**: Verify image URLs are proper format

---

## ✨ Next Steps for Backend Integration

1. Update `newsService.js` to call real API endpoints
2. Create MongoDB schema for articles
3. Build API endpoints:
   - GET /api/news/global
   - GET /api/news/india
   - GET /api/news/recommended
   - GET /api/news/for-you
   - GET /api/news/filter
   - GET /api/news/search
   - GET /api/news/:id
   - POST /api/news/refresh

4. Test with real data
5. Optimize performance if needed
6. Add pagination for large datasets
7. Implement real-time updates if desired

---

## 📞 Quick References

**Mock Data File**: `src/data/newsData.js`
**Service Layer**: `src/services/newsService.js`
**Main Component**: `src/components/Dashboard/TrendingNews.jsx`
**Styles**: `src/components/Dashboard/TrendingNews.css`

---

**Status**: ✅ Ready for Testing
**Last Updated**: September 2, 2026
