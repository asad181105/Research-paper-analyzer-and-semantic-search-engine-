import { useSearchParams } from "react-router-dom";
import ChatPanel from "../components/ChatPanel";

export default function Ask() {
  const [params] = useSearchParams();
  const paper = params.get("paper");
  return (
    <div>
      <h1 className="font-serif text-3xl">{paper ? "Ask this paper" : "Ask the library"}</h1>
      <p className="mt-2 text-sm text-stone-500">
        Answers are grounded in retrieved chunks with clickable citations.
      </p>
      <div className="mt-6 max-w-3xl">
        <ChatPanel paperId={paper ? Number(paper) : undefined} />
      </div>
    </div>
  );
}
