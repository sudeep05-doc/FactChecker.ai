const mongoose = require("mongoose");

const connectDB = async () => {
  const uri = process.env.MONGO_URI;

  if (!uri) {
    throw new Error("MongoDB connection failed. Check MONGO_URI in .env.");
  }

  mongoose.set("strictQuery", true);

  try {
    // dbName keeps local and Atlas URIs on the VerifyAI database, even when
    // the connection string omits a database name.
    await mongoose.connect(uri, { dbName: "verifyai" });
    console.log(`MongoDB connected: ${mongoose.connection.name}`);
  } catch (err) {
    // Do not include the driver error here: it can contain parts of a URI.
    throw new Error("MongoDB connection failed. Check MONGO_URI in .env.");
  }
};

module.exports = connectDB;
