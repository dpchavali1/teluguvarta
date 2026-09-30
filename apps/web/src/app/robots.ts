import type { MetadataRoute } from "next";

import { siteUrl } from "@/lib/api";
import { NOT_INDEXED } from "@/lib/sitemap";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: { userAgent: "*", allow: "/", disallow: NOT_INDEXED },
    sitemap: `${siteUrl()}/sitemap.xml`,
  };
}
