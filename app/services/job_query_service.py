from ..models import ExportJob, GenerationJob


class JobQueryService:
    def get_job(self, job_id: int):
        generation_job = GenerationJob.query.filter(GenerationJob.id == job_id).first()
        if generation_job:
            return {"kind": "generation", "job": generation_job}

        export_job = ExportJob.query.filter(ExportJob.id == job_id).first()
        if export_job:
            return {"kind": "export", "job": export_job}

        return None
