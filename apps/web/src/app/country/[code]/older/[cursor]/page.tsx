import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { pathParam } from "@/lib/pathParam";

import { CountryFeed, countryMetadata } from "../../CountryFeed";

export const revalidate = 60;

type Props = { params: Promise<{ code: string; cursor: string }> };

// Nothing prebuilt; each page renders on first request, then is cached.
export async function generateStaticParams() {
  return [];
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  return countryMetadata((await params).code.toUpperCase());
}

export default async function OlderCountryPage({ params }: Props) {
  const { code, cursor: raw } = await params;
  const cursor = pathParam(raw);
  if (!cursor) notFound();
  return <CountryFeed code={code.toUpperCase()} cursor={cursor} />;
}
