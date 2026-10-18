"""Conservative pre-playback companion-scope check for finalized caller text."""

import re

_SHOW = re.compile(
    r"\b(?:tv|show|serial|series|movie|film|cinema|drishyam|taarak|mehta|wwe)\b"
    r"|टीवी|फ़िल्म|फिल्म|मूवी|शो|सीरियल|तारक|मेहता|दृश्यम", re.I,
)
_SHOW_FACT = re.compile(
    r"\b(?:character|cast|actor|actress|star|director|plot|story|ending|release|award|"
    r"episode|season|review|rating|genre|suspense|funny|good|bad|about|kirdaar|"
    r"kirdar|kalakar|hero|heroine|kahani|kaun|kaisi|kaisa)\b"
    r"|किरदार|कलाकार|अभिनेता|हीरो|निर्देशक|कहानी|कौन|कैसी|कैसा", re.I,
)
_ASK = re.compile(
    r"\?|？|؟|\b(?:who|what|which|when|where|why|how|tell|know|explain|describe|"
    r"search|pata|bata|kaun|kon|kya|kis|jaante|jante|malum)\b"
    r"|क्या|कौन|कैसे|कब|कहां|बताओ|बताना|पता|जानते|जानती|मालूम|समझाओ", re.I,
)
_EXTERNAL = re.compile(
    r"\b(?:math|maths|algebra|equation|science|physics|chemistry|biology|gravity|"
    r"photosynthesis|history|geography|homework|exam|definition|politic\w*|election|"
    r"minister|president|news|weather forecast|code|coding|program|python|c\+\+|"
    r"javascript|wifi|wi-fi|troubleshoot|repair|recipe|how to|recommend|compare|"
    r"best phone|buy|price|stock|investment|tax|law|medicine|medication|dosage|diagnos\w*)\b"
    r"|गणित|विज्ञान|इतिहास|भूगोल|होमवर्क|राजनीति|चुनाव|समाचार|खबर|कोड|दवा|"
    r"इलाज|कैसे बनाएं|कौन सा खरीदें", re.I,
)
_TASK = re.compile(
    r"\b(?:search|google|look up|find out|write (?:me )?(?:a |the )?(?:code|program|essay|message)|"
    r"solve|calculate|translate|summarize (?:the |this )?(?:news|article)|"
    r"give me (?:the |a )?(?:facts?|answer|instructions?|recipe))\b"
    r"|गूगल|सर्च|हल करो|अनुवाद करो|लिख दो|समझाओ", re.I,
)
_GENERAL_FACT = re.compile(
    r"\b(?:what(?:'s| is| are)|who(?:'s| is)|tell me about|do you know|"
    r"can you explain|can you tell me (?:about|who|what|how))\b"
    r"|(?:क्या|कौन) (?:है|था)|(?:के|की) बारे में (?:बताओ|पता)", re.I,
)
_PERSONAL = re.compile(
    r"\b(?:my|mine|your|yours|us|our|we|family|background|memory|chat|day|"
    r"feeling|feel|think|opinion|like|enjoy)\b"
    r"|मेरे|मेरा|मेरी|मुझ|तुम|आप|हम|घर|परिवार|पसंद|लगता|लगी", re.I,
)
_ABOUT = re.compile(r"\b(?:about|baare|bare|mein)\b|बारे|में", re.I)
_HINGLISH = re.compile(r"\b(?:kya|kaun|kon|pata|bata|kirdaar|baare|bare|mein|aap|tum|hai|ho)\b", re.I)
_HINDI = re.compile(r"[\u0900-\u097f]")
_IDENTITY = re.compile(
    r"\b(?:who are you|what are you|are you (?:an? )?(?:ai|human)|what is hugback|"
    r"tum kaun ho|aap kaun ho)\b|आप कौन हैं|तुम कौन हो|क्या आप एआई", re.I,
)
_MEDICAL = re.compile(r"\b(?:medicine|medication|dosage|diagnos\w*|treatment|remedy)\b|दवा|इलाज", re.I)


class CompanionScopeGate:
    """High-confidence task detection; not a general semantic classifier."""

    def __init__(self) -> None:
        self.recent_entertainment = False
        self._turns_since_entertainment = 0

    def inspect(self, user_text: str) -> str | None:
        text = user_text.strip()
        if _IDENTITY.search(text):
            return None
        has_show = bool(_SHOW.search(text))
        in_show_context = has_show or self.recent_entertainment
        asks = bool(_ASK.search(text))
        asks_show = in_show_context and asks and (
            bool(_SHOW_FACT.search(text)) or bool(_ABOUT.search(text)) or has_show
        )
        asks_external = asks and bool(_EXTERNAL.search(text))
        direct_task = bool(_TASK.search(text))
        general_fact = bool(_GENERAL_FACT.search(text)) and not bool(_PERSONAL.search(text))

        if has_show:
            self.recent_entertainment = True
            self._turns_since_entertainment = 0
        elif self.recent_entertainment:
            self._turns_since_entertainment += 1
            if self._turns_since_entertainment > 3:
                self.recent_entertainment = False

        if not (asks_show or asks_external or direct_task or general_fact):
            return None
        if _MEDICAL.search(text):
            if _HINDI.search(text):
                return "दवा की सलाह डॉक्टर से लीजिए। तबीयत खराब है तो उनसे बात कीजिए।"
            if _HINGLISH.search(text):
                return "Dawa ki salah doctor se lijiye. Tabiyat kharab hai toh unse baat kijiye."
            return "I can't advise on medicine. If you're unwell, please speak with a doctor."
        if not asks_show:
            if _HINDI.search(text):
                return "उस सवाल के तथ्य छोड़िए। आप मुझे बताइए, ये बात कैसे आई?"
            if _HINGLISH.search(text):
                return "Us sawaal ke facts chhodiye. Yeh baat kaise aayi?"
            return "I won't give facts on that. What brought it up for you?"
        if _HINDI.search(text):
            return "उसके तथ्य छोड़िए। आपको उसमें क्या अच्छा लगा?"
        if _HINGLISH.search(text):
            return "Uske facts chhodiye. Aapko usmein kya achha laga?"
        return "I won't give facts about that. What did you enjoy about it?"


# Compatibility for existing imports.
EntertainmentScopeGate = CompanionScopeGate
