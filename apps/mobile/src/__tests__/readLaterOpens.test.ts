import * as Notifications from "expo-notifications";

import { listenForReadLaterOpens } from "../lib/readLater";

jest.mock("expo-notifications", () => ({
  getLastNotificationResponseAsync: jest.fn(),
  addNotificationResponseReceivedListener: jest.fn(),
  SchedulableTriggerInputTypes: { DATE: "date" },
}));

type Handler = (response: unknown) => void;

function response(id: string, trigger: { type: string }, data: Record<string, unknown>) {
  return { notification: { request: { identifier: id, trigger, content: { data } } } };
}

describe("listenForReadLaterOpens", () => {
  let handler: Handler = () => undefined;
  const remove = jest.fn();

  beforeEach(() => {
    jest.mocked(Notifications.getLastNotificationResponseAsync).mockResolvedValue(null);
    jest.mocked(Notifications.addNotificationResponseReceivedListener).mockImplementation(((h: Handler) => {
      handler = h;
      return { remove };
    }) as never);
  });

  it("opens the story for a tapped reminder, once", () => {
    const onOpen = jest.fn();
    listenForReadLaterOpens(onOpen);
    handler(response("a", { type: "date" }, { story_slug: "my-story" }));
    handler(response("a", { type: "date" }, { story_slug: "my-story" }));
    expect(onOpen).toHaveBeenCalledTimes(1);
    expect(onOpen).toHaveBeenCalledWith({ story_slug: "my-story" });
  });

  it("applies a cold-start tap", async () => {
    jest.mocked(Notifications.getLastNotificationResponseAsync).mockResolvedValue(
      response("cold", { type: "date" }, { story_slug: "cold-story" }) as never
    );
    const onOpen = jest.fn();
    listenForReadLaterOpens(onOpen);
    await new Promise((resolve) => setImmediate(resolve));
    expect(onOpen).toHaveBeenCalledWith({ story_slug: "cold-story" });
  });

  it("ignores pushes and responses without a story, and unsubscribes", () => {
    const onOpen = jest.fn();
    const stop = listenForReadLaterOpens(onOpen);
    handler(response("p", { type: "push" }, { story_slug: "x" }));
    handler(response("n", { type: "date" }, {}));
    expect(onOpen).not.toHaveBeenCalled();
    stop();
    expect(remove).toHaveBeenCalled();
  });
});
