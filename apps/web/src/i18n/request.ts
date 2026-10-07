import { getRequestConfig } from "next-intl/server";

// V1A-0: fixed single locale (routing/locale switching arrives with the
// website/content packet). The i18n foundation is next-intl.
export default getRequestConfig(async () => {
  return {
    locale: "en",
    messages: (await import("../../messages/en.json")).default,
  };
});
