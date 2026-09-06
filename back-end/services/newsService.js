const News = require("../models/News");

const createNews = async (payload) => {
  return News.create(payload);
};

const listNews = async () => {
  return News.find().sort({ createdAt: -1 });
};

const getNewsById = async (id) => {
  return News.findById(id);
};

module.exports = {
  createNews,
  listNews,
  getNewsById,
};
