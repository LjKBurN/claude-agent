import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    return [
      {
        source: "/api/:path*",
        destination: `${apiUrl}/api/:path*`,
      },
    ];
  },
  // 开发环境优化：减少不必要的编译开销
  devIndicators: false,
  staticPageGenerationTimeout: 60,
};

export default nextConfig;
