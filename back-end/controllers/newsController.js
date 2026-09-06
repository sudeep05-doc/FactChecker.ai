const { createNews, listNews, getNewsById } = require("../services/newsService");
const { success, error } = require("../utils/apiResponse");

const create = async (req, res, next) => {
  try {
    const { title, source, url, summary, category } = req.body;

    if (!title || !String(title).trim()) {
      return error(res, "News title is required.", 400);
    }

    const news = await createNews({
      title: String(title).trim(),
      source: source || "",
      url: url || "",
      summary: summary || "",
      category: category || "general",
      createdBy: req.user?._id || null,
    });

    return success(res, news, "News created.", 201);
  } catch (err) {
    next(err);
  }
};

const list = async (req, res, next) => {
  try {
    const news = await listNews();
    return success(res, news);
  } catch (err) {
    next(err);
  }
};

const getById = async (req, res, next) => {
  try {
    const news = await getNewsById(req.params.id);

    if (!news) {
      return error(res, "News item not found.", 404);
    }

    return success(res, news);
  } catch (err) {
    next(err);
  }
};

module.exports = {
  create,
  list,
  getById,
};
