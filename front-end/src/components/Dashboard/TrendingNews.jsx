import { useMemo, useState, useEffect } from "react";
import newsService from "../../services/newsService";
import "./TrendingNews.css";

/* =========================================================
   ARTICLE IMAGE COMPONENT
========================================================= */

function ArticleImage({ src, alt, className = "" }) {
  const [imageFailed, setImageFailed] = useState(false);

  return (
    <img
      className={`trending-image ${className}`}
      src={imageFailed ? undefined : src}
      alt={alt}
      loading="lazy"
      onError={() => {
        setImageFailed(true);
      }}
      style={imageFailed ? {
        display: "none",
      } : {}}
    />
  );
}

/* =========================================================
   TRENDING NEWS MAIN COMPONENT
========================================================= */

export default function TrendingNews({ setActiveView }) {
  // State Management
  const [tab, setTab] = useState("For You");
  const [category, setCategory] = useState("All Categories");
  const [refreshing, setRefreshing] = useState(false);
  const [savedArticles, setSavedArticles] = useState([]);
  const [likedArticles, setLikedArticles] = useState([]);
  const [activeSlide, setActiveSlide] = useState(0);
  const [topRegion, setTopRegion] = useState("Global");
  const [selectedArticle, setSelectedArticle] = useState(null);
  const [newsData, setNewsData] = useState({
    global: [],
    india: [],
    forYou: [],
    recommended: [],
  });
  const [loading, setLoading] = useState(true);

  // Load data on mount
  useEffect(() => {
    loadAllNews();
    loadSavedAndLiked();
  }, []);

  // Auto-slide hero every 5 seconds
  useEffect(() => {
    if (!selectedArticle) {
      const interval = setInterval(() => {
        setActiveSlide((prev) =>
          (prev + 1) % Math.max(filteredNews.length, 1)
        );
      }, 5000);
      return () => clearInterval(interval);
    }
  }, [selectedArticle]);

  // Load all news data
  const loadAllNews = async () => {
    setLoading(true);
    try {
      const [global, india, forYou, recommended] = await Promise.all([
        newsService.getGlobalNews(),
        newsService.getIndiaNews(),
        newsService.getForYouNews(),
        newsService.getRecommendedNews(),
      ]);
      setNewsData({ global, india, forYou, recommended });
    } catch (error) {
      console.error("Error loading news:", error);
    } finally {
      setLoading(false);
    }
  };

  // Load saved and liked from localStorage
  const loadSavedAndLiked = () => {
    const saved = localStorage.getItem(
      "verifyai_saved_articles"
    );
    const liked = localStorage.getItem(
      "verifyai_liked_articles"
    );
    if (saved) setSavedArticles(JSON.parse(saved));
    if (liked) setLikedArticles(JSON.parse(liked));
  };

  // Save to localStorage when state changes
  useEffect(() => {
    localStorage.setItem(
      "verifyai_saved_articles",
      JSON.stringify(savedArticles)
    );
  }, [savedArticles]);

  useEffect(() => {
    localStorage.setItem(
      "verifyai_liked_articles",
      JSON.stringify(likedArticles)
    );
  }, [likedArticles]);

  // Filter news based on tab and category
  const filteredNews = useMemo(() => {
    let result = [];

    if (tab === "For You") {
      result = newsData.forYou;
    } else if (tab === "Global") {
      result = newsData.global;
    } else if (tab === "India") {
      result = newsData.india;
    }

    if (category !== "All Categories") {
      result = result.filter(
        (item) => item.category === category
      );
    }

    return result.length ? result : [];
  }, [tab, category, newsData]);

  // Get hero article (featured article)
  const heroArticle =
    filteredNews.length > 0
      ? filteredNews[activeSlide % filteredNews.length]
      : null;

  // Toggle save/like with persistence
  const toggleSave = (articleId) => {
    setSavedArticles((prev) =>
      prev.includes(articleId)
        ? prev.filter((id) => id !== articleId)
        : [...prev, articleId]
    );
  };

  const toggleLike = (articleId) => {
    setLikedArticles((prev) =>
      prev.includes(articleId)
        ? prev.filter((id) => id !== articleId)
        : [...prev, articleId]
    );
  };

  // Open article details page
  const openArticle = (article) => {
    setSelectedArticle(article);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  // Close article details
  const closeArticle = () => {
    setSelectedArticle(null);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  // Refresh news
  const refreshNews = async () => {
    setRefreshing(true);
    try {
      await newsService.refreshNews();
      // Reshuffle the news
      await loadAllNews();
      setActiveSlide(0);
    } catch (error) {
      console.error("Error refreshing news:", error);
    } finally {
      setRefreshing(false);
    }
  };

  // If article is selected, show article reader
  if (selectedArticle) {
    return (
      <ArticleReader
        article={selectedArticle}
        onBack={closeArticle}
        onSave={toggleSave}
        onLike={toggleLike}
        isSaved={savedArticles.includes(
          selectedArticle.id
        )}
        isLiked={likedArticles.includes(
          selectedArticle.id
        )}
        setActiveView={setActiveView}
      />
    );
  }

  // Get sections data
  const globalItems = newsData.global
    .filter((item) => item.category !== "World")
    .slice(0, 6);
  const indiaItems = newsData.india.slice(0, 6);

  const categories = newsService.getCategories();

  return (
    <div className="trending-page">
      {/* HERO SECTION */}
      <section className="trending-hero-panel">
        <div className="trending-page-heading">
          <div>
            <div className="trending-title-row">
              <h2>Trending News</h2>
              <span className="trend-arrow">↗</span>
            </div>
            <p>
              Stay updated with what's happening around
              the world
            </p>
          </div>
          <span className="news-count">
            {filteredNews.length} stories
          </span>
        </div>

        {/* TOOLBAR */}
        <div className="trending-toolbar">
          <div className="news-tabs">
            {[
              ["For You", "🔥"],
              ["Global", "🌐"],
              ["India", "🇮🇳"],
            ].map(([name, icon]) => (
              <button
                key={name}
                className={
                  tab === name ? "active" : ""
                }
                onClick={() => {
                  setTab(name);
                  setCategory("All Categories");
                  setActiveSlide(0);
                }}
              >
                <span>{icon}</span> {name}
              </button>
            ))}
          </div>

          <div className="trending-actions">
            <label className="category-select">
              <span>☷</span>
              <select
                value={category}
                onChange={(e) => {
                  setCategory(e.target.value);
                  setActiveSlide(0);
                }}
              >
                {categories.map((item) => (
                  <option key={item}>
                    {item}
                  </option>
                ))}
              </select>
            </label>
            <button
              className={`refresh-btn ${
                refreshing ? "refreshing" : ""
              }`}
              onClick={refreshNews}
              disabled={refreshing}
            >
              ↻ <span>Refresh</span>
            </button>
          </div>
        </div>

        {/* HERO STORY CARD */}
        {heroArticle ? (
          <>
            <div className="hero-story-card">
              <div
                className="hero-story-image-wrap"
                onClick={() => openArticle(heroArticle)}
                style={{ cursor: "pointer" }}
              >
                <ArticleImage
                  src={heroArticle.image}
                  alt={heroArticle.title}
                />
                {heroArticle.breaking && (
                  <span className="breaking-badge">
                    BREAKING
                  </span>
                )}
                <div className="hero-image-meta">
                  <span>
                    {heroArticle.category}
                  </span>
                  <span>◷ {heroArticle.time}</span>
                  <span>
                    • {heroArticle.reads} reads
                  </span>
                </div>
              </div>

              <div className="hero-story-copy">
                <div className="story-actions">
                  <span>
                    ☆ {heroArticle.reads}
                  </span>
                  <button
                    onClick={() =>
                      toggleSave(heroArticle.id)
                    }
                  >
                    {savedArticles.includes(
                      heroArticle.id
                    )
                      ? "▣ Saved"
                      : "▢ Save"}
                  </button>
                </div>
                <h1>{heroArticle.title}</h1>
                <p>{heroArticle.description}</p>
                <div className="reader-row">
                  <div className="reader-avatars">
                    <i>R</i>
                    <i>A</i>
                    <i>S</i>
                  </div>
                  <span>
                    12.4K people reading
                  </span>
                  <button
                    onClick={() =>
                      openArticle(heroArticle)
                    }
                    className="read-story-btn"
                  >
                    Read Full Story{" "}
                    <b>→</b>
                  </button>
                </div>
              </div>
            </div>

            {/* HERO DOTS */}
            <div className="hero-dots">
              {filteredNews
                .slice(0, 8)
                .map((item, index) => (
                  <button
                    key={item.id}
                    aria-label={`Show story ${
                      index + 1
                    }`}
                    className={
                      index ===
                      activeSlide % 8
                        ? "active"
                        : ""
                    }
                    onClick={() =>
                      setActiveSlide(index)
                    }
                  />
                ))}
            </div>
          </>
        ) : (
          <div className="empty-state">
            <span>📰</span>
            <h2>No articles found</h2>
            <p>
              Try adjusting your filters or check
              back later
            </p>
          </div>
        )}
      </section>

      {/* MAIN GRID */}
      {filteredNews.length > 0 && (
        <div className="trending-main-grid">
          <div className="trending-left-column">
            {/* DUAL TRENDING GRID */}
            <div className="dual-trending-grid">
              <TrendingList
                title="Top Trending – Global 🌐"
                items={globalItems}
                saved={savedArticles}
                liked={likedArticles}
                onSave={toggleSave}
                onLike={toggleLike}
                onOpenArticle={openArticle}
                onViewAll={() => {
                  setTab("Global");
                  setCategory(
                    "All Categories"
                  );
                  setActiveSlide(0);
                }}
              />
              <TrendingList
                title="Top Trending – India 🇮🇳"
                items={indiaItems}
                saved={savedArticles}
                liked={likedArticles}
                onSave={toggleSave}
                onLike={toggleLike}
                onOpenArticle={openArticle}
                onViewAll={() => {
                  setTab("India");
                  setCategory(
                    "All Categories"
                  );
                  setActiveSlide(0);
                }}
              />
            </div>

            {/* ALL NEWS SECTION */}
            <section className="all-news-section">
              <div className="all-news-heading">
                <div>
                  <span className="section-kicker">
                    LATEST UPDATES
                  </span>
                  <h3>More Trending News</h3>
                  <p>
                    Browse the latest stories
                    across technology, business,
                    world news, India and more.
                  </p>
                </div>
                <span className="result-count">
                  {filteredNews.length} stories
                </span>
              </div>
              <div className="news-masonry-grid">
                {filteredNews.map((item) => (
                  <article
                    className="expanded-news-card"
                    key={item.id}
                  >
                    <div
                      className="expanded-news-image"
                      onClick={() =>
                        openArticle(item)
                      }
                      style={{
                        cursor: "pointer",
                      }}
                    >
                      <ArticleImage
                        src={item.image}
                        alt={item.title}
                      />
                      <span
                        className={`expanded-category ${item.category.toLowerCase().replace(
                          /\s+/g,
                          "-"
                        )}`}
                      >
                        {item.category}
                      </span>
                    </div>
                    <div className="expanded-news-body">
                      <div className="expanded-meta">
                        <span>{item.time}</span>
                        <span>•</span>
                        <span>
                          {item.reads} reads
                        </span>
                      </div>
                      <h4>{item.title}</h4>
                      <p>
                        {item.description}
                      </p>
                      <div className="expanded-actions">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            toggleLike(item.id);
                          }}
                          className={
                            likedArticles.includes(
                              item.id
                            )
                              ? "liked"
                              : ""
                          }
                        >
                          {likedArticles.includes(
                            item.id
                          )
                            ? "♥ Liked"
                            : "♡ Like"}
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            toggleSave(item.id);
                          }}
                        >
                          {savedArticles.includes(
                            item.id
                          )
                            ? "▣ Saved"
                            : "▢ Save"}
                        </button>
                        <button
                          className="read-link"
                          onClick={() =>
                            openArticle(item)
                          }
                        >
                          Read →
                        </button>
                      </div>
                    </div>
                  </article>
                ))}
              </div>
            </section>
          </div>

          {/* RIGHT SIDEBAR */}
          <aside className="trending-right-column">
            {/* RECOMMENDED */}
            <section className="recommended-card">
              <div className="side-card-heading">
                <h3>
                  Recommended for You
                </h3>
                <button
                  onClick={() =>
                    setTab("For You")
                  }
                >
                  View All
                </button>
              </div>
              {newsData.recommended
                .slice(0, 5)
                .map((item) => (
                  <article
                    className="recommended-item"
                    key={item.id}
                    onClick={() =>
                      openArticle(item)
                    }
                    style={{
                      cursor: "pointer",
                    }}
                  >
                    <div className="small-image-wrap">
                      <ArticleImage
                        src={item.image}
                        alt=""
                      />
                    </div>
                    <div className="recommended-copy">
                      <span
                        className={`news-category ${item.category.toLowerCase().replace(
                          /\s+/g,
                          "-"
                        )}`}
                      >
                        {item.category}
                      </span>
                      <h4>{item.title}</h4>
                      <p>
                        {item.time}{" "}
                        <b>•</b> {item.reads}{" "}
                        reads
                      </p>
                    </div>
                    <div className="item-icons">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          toggleLike(item.id);
                        }}
                        className={
                          likedArticles.includes(
                            item.id
                          )
                            ? "liked"
                            : ""
                        }
                      >
                        ♡
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          toggleSave(item.id);
                        }}
                      >
                        {savedArticles.includes(
                          item.id
                        )
                          ? "▣"
                          : "▢"}
                      </button>
                    </div>
                  </article>
                ))}
            </section>

            {/* TOP TRENDING */}
            <section className="top-trending-card">
              <div className="side-card-heading top-heading">
                <h3>Top Trending News</h3>
                <div>
                  <button
                    className={
                      topRegion === "Global"
                        ? "active"
                        : ""
                    }
                    onClick={() =>
                      setTopRegion("Global")
                    }
                  >
                    Global
                  </button>
                  <button
                    className={
                      topRegion === "India"
                        ? "active"
                        : ""
                    }
                    onClick={() =>
                      setTopRegion("India")
                    }
                  >
                    India
                  </button>
                </div>
              </div>
              {(topRegion === "Global"
                ? newsData.global
                : newsData.india
              )
                .slice(0, 10)
                .map((item, index) => (
                  <article
                    className="ranked-item"
                    key={`${topRegion}-${item.id}`}
                    onClick={() =>
                      openArticle(item)
                    }
                    style={{
                      cursor: "pointer",
                    }}
                  >
                    <strong>{index + 1}</strong>
                    <div className="rank-thumb">
                      <ArticleImage
                        src={item.image}
                        alt=""
                      />
                    </div>
                    <div className="rank-copy">
                      <h4>{item.title}</h4>
                      <p>
                        {item.time}{" "}
                        <b>•</b> {item.reads}{" "}
                        reads
                      </p>
                    </div>
                    <span className="direction up">
                      ↗
                    </span>
                  </article>
                ))}
              <button className="view-trending-btn">
                View All Trending{" "}
                <span>→</span>
              </button>
            </section>
          </aside>
        </div>
      )}

      {/* POPULAR TOPICS */}
      <section className="popular-topics">
        <strong>
          <span>#</span> Popular Topics
        </strong>
        {[
          "# AI & Technology",
          "# Stock Market",
          "# IPL 2025",
          "# Climate Change",
          "# Budget 2025",
          "# World Politics",
        ].map((topic) => (
          <button
            key={topic}
            onClick={async () => {
              const results =
                await newsService.searchNews(
                  topic.replace("# ", "")
                );
              // Filter news to show search results
            }}
          >
            {topic}
          </button>
        ))}
        <button className="topics-next">
          ›
        </button>
      </section>
    </div>
  );
}

/* =========================================================
   TRENDING LIST COMPONENT
========================================================= */

function TrendingList({
  title,
  items,
  saved,
  liked,
  onSave,
  onLike,
  onOpenArticle,
  onViewAll,
}) {
  return (
    <section className="trending-list-card">
      <div className="list-heading">
        <h3>{title}</h3>
        <button onClick={onViewAll}>
          View All
        </button>
      </div>
      {items.map((item) => (
        <article
          className="trending-list-item"
          key={item.id}
          onClick={() => onOpenArticle(item)}
          style={{ cursor: "pointer" }}
        >
          <div className="list-thumb">
            <ArticleImage
              src={item.image}
              alt=""
            />
          </div>
          <div className="list-copy">
            <span
              className={`news-category ${item.category.toLowerCase().replace(
                /\s+/g,
                "-"
              )}`}
            >
              {item.category}
            </span>
            <h4>{item.title}</h4>
            <p>
              {item.time} <b>•</b> {item.reads}{" "}
              reads
            </p>
          </div>
          <div className="item-icons">
            <button
              onClick={(e) => {
                e.stopPropagation();
                onLike(item.id);
              }}
              className={
                liked.includes(item.id)
                  ? "liked"
                  : ""
              }
            >
              ♡
            </button>
            <button
              onClick={(e) => {
                e.stopPropagation();
                onSave(item.id);
              }}
            >
              {saved.includes(item.id)
                ? "▣"
                : "▢"}
            </button>
          </div>
        </article>
      ))}
      <button
        className="list-footer-btn"
        onClick={onViewAll}
      >
        View All News <span>→</span>
      </button>
    </section>
  );
}

/* =========================================================
   ARTICLE READER COMPONENT
========================================================= */

function ArticleReader({
  article,
  onBack,
  onSave,
  onLike,
  isSaved,
  isLiked,
  setActiveView,
}) {
  return (
    <div className="article-reader-page">
      {/* Header */}
      <header className="article-reader-header">
        <button
          type="button"
          className="article-back-btn"
          onClick={onBack}
        >
          ← Back to Trending
        </button>

        <span className="article-reader-brand">
          Fact<span>Checker</span>
        </span>
      </header>

      {/* Content */}
      <main className="article-reader-content">
        <div className="article-breadcrumb">
          Trending News{" "}
          <span>›</span> {article.category}
        </div>

        <div className="article-category">
          {article.category}
        </div>

        <h1>{article.title}</h1>

        <p className="article-reader-description">
          {article.description}
        </p>

        <div className="article-reader-meta">
          <span>◷ {article.time}</span>
          <span>•</span>
          <span>
            👁 {article.reads} reads
          </span>
          <span>•</span>
          <span>{article.source}</span>
        </div>

        {/* Image */}
        <div className="article-reader-image">
          <ArticleImage
            src={article.image}
            alt={article.title}
          />
        </div>

        {/* Body */}
        <article className="article-body">
          <p>
            The latest developments
            surrounding this story are
            attracting significant attention from
            readers around the world. Here's what
            you need to know about the latest
            update.
          </p>

          <h2>What's happening?</h2>

          <p>
            {article.description} The
            development is being closely
            followed by experts, organizations
            and the public as more information
            becomes available.
          </p>

          <p>
            According to the latest reports, the
            situation continues to develop.
            Officials and analysts are
            monitoring new information and
            evaluating what it could mean in the
            coming days.
          </p>

          <div className="article-highlight">
            <span>✓</span>

            <div>
              <strong>
                FactChecker Insight
              </strong>

              <p>
                Always verify important claims
                using multiple reliable sources
                before sharing information.
              </p>
            </div>
          </div>

          <h2>Why it matters</h2>

          <p>
            This story could have an impact
            beyond the immediate event.
            Understanding the available
            evidence and separating confirmed
            information from speculation is
            important when following developing
            news.
          </p>

          <p>
            FactChecker will continue
            monitoring this story and provide
            updates as new verified information
            becomes available.
          </p>
        </article>

        {/* Actions */}
        <div className="article-reader-actions">
          <button
            type="button"
            onClick={() => onLike(article.id)}
            className={
              isLiked ? "liked" : ""
            }
          >
            {isLiked ? "♥ Liked" : "♡ Like"}
          </button>

          <button
            type="button"
            onClick={() => onSave(article.id)}
          >
            {isSaved
              ? "🔖 Saved"
              : "🔖 Save Article"}
          </button>

          <button type="button">↗ Share</button>

          <button
            type="button"
            onClick={() =>
              setActiveView("analyze")
            }
            className="verify-button"
          >
            Verify →
          </button>
        </div>

        {/* Back button */}
        <button
          type="button"
          className="article-bottom-back"
          onClick={onBack}
        >
          ← Back to Trending News
        </button>
      </main>
    </div>
  );
}
