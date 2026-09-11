import TrackClient from "./track-client";

export async function generateStaticParams() {
  return [{ id: "demo" }];
}

export default function TrackPage() {
  return <TrackClient />;
}