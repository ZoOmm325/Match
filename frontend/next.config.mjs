/** @type {import('next').NextConfig} */
const isDevelopment = process.env.NODE_ENV === "development";

const nextConfig = {
  reactStrictMode: true,
  distDir: isDevelopment ? process.env.NEXT_DEV_DIST_DIR || ".next-dev" : ".next",
  ...(isDevelopment ? {} : { output: "standalone" }),
};

export default nextConfig;
