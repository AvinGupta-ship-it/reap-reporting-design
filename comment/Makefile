# Builds the Paperwork Reduction Act comment (PDF and DOCX) and its technical attachment.
.PHONY: all clean
all: comment.pdf comment.docx attachment_technical.pdf

%.pdf: %.tex ../paper/generated/values.tex ../paper/references.bib
	latexmk -pdf -interaction=nonstopmode -halt-on-error $<

comment.docx: comment.tex ../paper/generated/values.tex
	sed -E 's/\\label\{eq:[a-z]+\}//' comment.tex | pandoc --from=latex --to=docx --citeproc \
		--bibliography=../paper/references.bib --resource-path=.:../paper:../paper/figures \
		--default-image-extension=png -o comment.docx

clean:
	latexmk -C
