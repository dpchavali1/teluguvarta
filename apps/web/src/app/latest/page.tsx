import { LatestFeed } from "./LatestFeed";

export const metadata = { title: "Latest stories" };
export const revalidate = 60;

export default function LatestPage() {
  return <LatestFeed />;
}
