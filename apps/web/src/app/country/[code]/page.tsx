import type { Metadata } from "next";

import { CountryFeed, countryMetadata } from "./CountryFeed";

export const revalidate = 60;

type Props = { params: Promise<{ code: string }> };

// Nothing prebuilt; each country renders on first request, then is cached.
export async function generateStaticParams() {
  return [];
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  return countryMetadata((await params).code.toUpperCase());
}

export default async function CountryPage({ params }: Props) {
  return <CountryFeed code={(await params).code.toUpperCase()} />;
}
